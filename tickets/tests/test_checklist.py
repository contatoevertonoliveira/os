
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from tickets.models import UserProfile, ChecklistTemplate, ChecklistTemplateItem, DailyChecklist, DailyChecklistItem
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

class ChecklistTests(TestCase):
    def setUp(self):
        # Create Admin User
        self.username_admin = f'admin_{timezone.now().timestamp()}'
        self.admin_user = User.objects.create_user(username=self.username_admin, password='password')
        self.admin_profile = UserProfile.objects.create(user=self.admin_user, role='admin', department='IT')
        
        # Create Technician User
        self.username_tech = f'tech_{timezone.now().timestamp()}'
        self.tech_user = User.objects.create_user(username=self.username_tech, password='password')
        self.tech_profile = UserProfile.objects.create(user=self.tech_user, role='technician', department='IT')
        
        # Create Checklist Template
        self.template = ChecklistTemplate.objects.create(name='IT Daily', department='IT')
        self.item1 = ChecklistTemplateItem.objects.create(template=self.template, description='Check backups', order=1)
        self.item2 = ChecklistTemplateItem.objects.create(template=self.template, description='Check servers', order=2)

    def test_checklist_daily_view_creates_checklist(self):
        client = Client()
        client.force_login(self.tech_user)
        
        response = client.get(reverse('checklist_daily'))
        self.assertEqual(response.status_code, 200)
        
        # Check if checklist was created
        today = timezone.now().date()
        checklist = DailyChecklist.objects.filter(user=self.tech_user, date=today).first()
        self.assertIsNotNone(checklist)
        self.assertEqual(checklist.items.count(), 2)

    def test_checklist_config_view_access_control(self):
        client = Client()
        
        # Test admin access
        client.force_login(self.admin_user)
        response = client.get(reverse('checklist_config'))
        self.assertEqual(response.status_code, 200)
        
        response = client.get(reverse('checklist_template_create'))
        self.assertEqual(response.status_code, 200)
        
        response = client.get(reverse('checklist_template_edit', args=[self.template.id]))
        self.assertEqual(response.status_code, 200)
        
        # Test technician access (should be denied)
        client.force_login(self.tech_user)
        response = client.get(reverse('checklist_config'))
        self.assertEqual(response.status_code, 403)
        
        response = client.get(reverse('checklist_template_create'))
        self.assertEqual(response.status_code, 403)
        
        response = client.get(reverse('checklist_template_edit', args=[self.template.id]))
        self.assertEqual(response.status_code, 403)

    def test_checklist_pdf_generation(self):
        client = Client()
        client.force_login(self.tech_user)
        
        # Create checklist first
        checklist = DailyChecklist.objects.create(
            user=self.tech_user, 
            date=timezone.now().date(),
            template=self.template
        )
        DailyChecklistItem.objects.create(daily_checklist=checklist, description='Task 1', is_checked=True)
        
        response = client.get(reverse('checklist_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_checklist_image_upload(self):
        client = Client()
        client.force_login(self.tech_user)
        
        # Initialize checklist
        client.get(reverse('checklist_daily'))
        checklist = DailyChecklist.objects.get(user=self.tech_user, date=timezone.now().date())
        item = checklist.items.first()
        
        # Prepare form data
        # Minimal valid GIF
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        image_file = SimpleUploadedFile("test_image.gif", image_content, content_type="image/gif")
        
        data = {
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '2',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-id': item.id,
            'items-0-is_checked': 'on',
            'items-0-observation': 'Done',
            'items-0-image': image_file,
            'items-1-id': checklist.items.last().id,
            'items-1-observation': '',
        }
        
        response = client.post(reverse('checklist_daily'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify changes
        item.refresh_from_db()
        self.assertTrue(item.is_checked)
        self.assertEqual(item.observation, 'Done')
        self.assertTrue(item.image)
