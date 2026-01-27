from django.test import TestCase, Client as DjangoClient
from django.urls import reverse
from django.contrib.auth.models import User
from tickets.models import Client, ClientHub, Ticket, TicketType, TechnicianTravel, TravelSegment
from django.utils import timezone
import datetime

class ClientSearchViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        
        self.client_obj = Client.objects.create(
            name='Test Client',
            city='Test City',
            cm_code='12345',
            group='Test Group'
        )
        self.client2 = Client.objects.create(
            name='Another Client',
            city='Other City',
            cm_code='67890',
            group='Other Group'
        )

    def test_search_by_name(self):
        response = self.client.get(reverse('client_search'), {'q': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Client')
        self.assertNotContains(response, 'Another Client')

    def test_search_by_city(self):
        response = self.client.get(reverse('client_search'), {'q': 'Other City'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Another Client')
        self.assertNotContains(response, 'Test Client')

    def test_search_by_cm_code(self):
        response = self.client.get(reverse('client_search'), {'q': '12345'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Client')

class HubDashboardViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        
        self.client_obj = Client.objects.create(name='Test Client')
        self.hub = ClientHub.objects.create(
            name='Test Hub',
            client=self.client_obj,
            address='Hub Address'
        )
        self.ticket_type = TicketType.objects.create(name='Preventiva')
        self.ticket = Ticket.objects.create(
            client=self.client_obj,
            hub=self.hub,
            ticket_type=self.ticket_type,
            status='open',
            description='Test Ticket'
        )

    def test_dashboard_access(self):
        response = self.client.get(reverse('hub_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Hub')

    def test_dashboard_filtering(self):
        # Create another client and hub
        client2 = Client.objects.create(name='Client 2')
        hub2 = ClientHub.objects.create(name='Hub 2', client=client2)
        
        response = self.client.get(reverse('hub_dashboard'), {'client': self.client_obj.id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Hub')
        self.assertNotContains(response, 'Hub 2')
