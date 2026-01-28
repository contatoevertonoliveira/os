
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from tickets.models import Client, ClientHub, Ticket, TicketType, UserProfile, TechnicianTravel, TravelSegment, System
from tickets.views import HubDashboardView
import datetime

class HubDashboardLogicTest(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(username='testuser', password='password')
        UserProfile.objects.create(user=self.user, role='admin')
        
        # Create client
        self.client = Client.objects.create(name="Test Client")
        
        # Create hub
        self.hub = ClientHub.objects.create(client=self.client, name="Test Hub")
        
        # Create ticket type
        self.ticket_type = TicketType.objects.create(name="Manutenção")
        
        # Create Ticket
        self.ticket = Ticket.objects.create(
            client=self.client,
            hub=self.hub,
            ticket_type=self.ticket_type,
            requester=self.user,
            description="Test Ticket",
            status='open'
        )
        self.ticket.technicians.add(self.user)
        
        # Create Travel
        self.travel = TechnicianTravel.objects.create(
            client=self.client,
            hub=self.hub,
            technician=self.user,
            service_order=self.ticket,
            scheduled_date=timezone.now(),
            status='confirmed'
        )
        
        # Create Segment
        self.segment = TravelSegment.objects.create(
            travel=self.travel,
            transport_type='air',
            carrier='GOL',
            transport_number='G3 1234',
            origin='GRU',
            destination='REC',
            departure_time=timezone.now(),
            arrival_time=timezone.now() + datetime.timedelta(hours=3),
            booking_code='ABC123456',
            locator='XYZ789',
            seat='12A'
        )

    def test_context_data_population(self):
        factory = RequestFactory()
        request = factory.get('/dashboard/hubs/')
        request.user = self.user
        
        view = HubDashboardView()
        view.setup(request)
        
        context = view.get_context_data()
        
        # Check dashboard_items
        dashboard_items = context.get('dashboard_items', [])
        self.assertTrue(len(dashboard_items) > 0, "Dashboard items should not be empty")
        
        # Check if client and hub are present
        client_found = any(item['type'] == 'client' and item['id'] == self.client.id for item in dashboard_items)
        hub_found = any(item['type'] == 'hub' and item['id'] == self.hub.id for item in dashboard_items)
        
        self.assertTrue(client_found, "Client card should be present")
        self.assertTrue(hub_found, "Hub card should be present")
        
        # Check hubs_data map
        hubs_data = context.get('hubs_data', {})
        self.assertIn(f'hub_{self.hub.id}', hubs_data)
        
        # Verify Travel Details in Payload
        hub_payload = hubs_data[f'hub_{self.hub.id}']
        agendadas = hub_payload.get('agendadas', [])
        
        # Find our ticket
        ticket_item = next((t for t in agendadas if t['id'] == self.ticket.id), None)
        self.assertIsNotNone(ticket_item, "Ticket should be in agendadas")
        
        # Verify Travel Payload
        travel_data = ticket_item.get('travel')
        self.assertIsNotNone(travel_data, "Travel data should be present")
        self.assertTrue(travel_data['segment_exists'])
        self.assertEqual(travel_data['carrier'], 'GOL')
        self.assertEqual(travel_data['transport_number'], 'G3 1234')
        self.assertEqual(travel_data['origin'], 'GRU')
        self.assertEqual(travel_data['destination'], 'REC')
        self.assertEqual(travel_data['locator'], 'XYZ789')
        self.assertEqual(travel_data['booking_code'], 'ABC123456')
        self.assertEqual(travel_data['seat'], '12A')
        self.assertEqual(travel_data['duration'], '03h 00min')
