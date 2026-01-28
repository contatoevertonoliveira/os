from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    DashboardView, HubDashboardView, TicketListView, TicketCreateView, TicketUpdateView, TicketDeleteView, TicketDetailView, TicketModalView, TokenLoginView,
    ClientListView, ClientCreateView, ClientUpdateView, ClientDeleteView, ClientSearchView,
    EquipmentListView, EquipmentCreateView, EquipmentUpdateView, EquipmentDeleteView,
    OrderTypeListView, OrderTypeCreateView, OrderTypeUpdateView, OrderTypeDeleteView,
    ProblemTypeListView, ProblemTypeCreateView, ProblemTypeUpdateView, ProblemTypeDeleteView,
    TechnicianListView, TechnicianCreateView, TechnicianUpdateView, TechnicianDeleteView,
    TechnicianTravelListView, TechnicianTravelDetailView, TechnicianTravelCreateView, TechnicianTravelUpdateView, TechnicianTravelDeleteView, TechnicianTravelCompleteView,
    TravelSegmentCreateView, TravelSegmentUpdateView, TravelSegmentDeleteView,
    SystemListView, SystemCreateView, SystemUpdateView, SystemDeleteView,
    UserListView, UserCreateView, UserUpdateView, UserDeleteView,
    ProfileView, SettingsView,
    TaskListView, TaskFavoriteView,
    NotificationListView, SendMessageView, NotificationMonitorView, mark_notification_read, mark_all_notifications_read,
    load_hubs, ChecklistDailyView, ChecklistPDFView,
    ChecklistConfigView, ChecklistTemplateCreateView, ChecklistTemplateUpdateView, ChecklistTemplateDeleteView, ChecklistItemCreateView, ChecklistItemDeleteView
)
from .api import TicketAPIView, ClientAPIView, EquipmentAPIView

urlpatterns = [
    path('api/tickets/', TicketAPIView.as_view(), name='api_tickets'),
    path('api/clients/', ClientAPIView.as_view(), name='api_clients'),
    path('api/equipments/', EquipmentAPIView.as_view(), name='api_equipments'),
    path('ajax/load-hubs/', load_hubs, name='ajax_load_hubs'),
    path('', DashboardView.as_view(), name='dashboard'),
    
    # Tasks
    path('tasks/', TaskListView.as_view(), name='task_list'),
    path('tasks/<int:pk>/favorite/', TaskFavoriteView.as_view(), name='task_favorite'),
    
    # Checklist
    path('checklist/daily/', ChecklistDailyView.as_view(), name='checklist_daily'),
    path('checklist/daily/pdf/', ChecklistPDFView.as_view(), name='checklist_pdf'),
    path('checklist/config/', ChecklistConfigView.as_view(), name='checklist_config'),
    path('checklist/config/new/', ChecklistTemplateCreateView.as_view(), name='checklist_template_create'),
    path('checklist/config/<int:pk>/edit/', ChecklistTemplateUpdateView.as_view(), name='checklist_template_edit'),
    path('checklist/config/<int:pk>/delete/', ChecklistTemplateDeleteView.as_view(), name='checklist_template_delete'),
    path('checklist/config/<int:pk>/items/add/', ChecklistItemCreateView.as_view(), name='checklist_item_add'),
    path('checklist/config/items/<int:pk>/delete/', ChecklistItemDeleteView.as_view(), name='checklist_item_delete'),

    # Dashboard Hubs
    path('dashboard/hubs/', HubDashboardView.as_view(), name='hub_dashboard'),

    path('profile/', ProfileView.as_view(), name='profile'),
    path('settings/', SettingsView.as_view(), name='settings'),
    path('login/', TokenLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    
    path('tickets/', TicketListView.as_view(), name='ticket_list'),
    path('tickets/new/', TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/<int:pk>/', TicketDetailView.as_view(), name='ticket_detail'),
    path('tickets/<int:pk>/modal/', TicketModalView.as_view(), name='ticket_modal'),
    path('tickets/<int:pk>/edit/', TicketUpdateView.as_view(), name='ticket_update'),
    path('tickets/<int:pk>/delete/', TicketDeleteView.as_view(), name='ticket_delete'),
    
    # Evolution Updates
    # path('updates/<int:pk>/edit/', TicketUpdateEditView.as_view(), name='ticket_update_edit'),
    # path('updates/<int:pk>/delete/', TicketUpdateDeleteView.as_view(), name='ticket_update_delete'),

    # Cadastros
    path('clients/', ClientListView.as_view(), name='client_list'),
    path('clients/search/', ClientSearchView.as_view(), name='client_search'),
    path('clients/new/', ClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/edit/', ClientUpdateView.as_view(), name='client_update'),
    path('clients/<int:pk>/delete/', ClientDeleteView.as_view(), name='client_delete'),

    path('equipments/', EquipmentListView.as_view(), name='equipment_list'),
    path('equipments/new/', EquipmentCreateView.as_view(), name='equipment_create'),
    path('equipments/<int:pk>/edit/', EquipmentUpdateView.as_view(), name='equipment_update'),
    path('equipments/<int:pk>/delete/', EquipmentDeleteView.as_view(), name='equipment_delete'),

    path('ordertypes/', OrderTypeListView.as_view(), name='ordertype_list'),
    path('ordertypes/new/', OrderTypeCreateView.as_view(), name='ordertype_create'),
    path('ordertypes/<int:pk>/edit/', OrderTypeUpdateView.as_view(), name='ordertype_update'),
    path('ordertypes/<int:pk>/delete/', OrderTypeDeleteView.as_view(), name='ordertype_delete'),

    path('problemtypes/', ProblemTypeListView.as_view(), name='problemtype_list'),
    path('problemtypes/new/', ProblemTypeCreateView.as_view(), name='problemtype_create'),
    path('problemtypes/<int:pk>/edit/', ProblemTypeUpdateView.as_view(), name='problemtype_update'),
    path('problemtypes/<int:pk>/delete/', ProblemTypeDeleteView.as_view(), name='problemtype_delete'),

    path('technicians/', TechnicianListView.as_view(), name='technician_list'),
    path('technicians/new/', TechnicianCreateView.as_view(), name='technician_create'),
    path('technicians/<int:pk>/edit/', TechnicianUpdateView.as_view(), name='technician_update'),
    path('technicians/<int:pk>/delete/', TechnicianDeleteView.as_view(), name='technician_delete'),

    path('travels/', TechnicianTravelListView.as_view(), name='travel_list'),
    path('travels/<int:pk>/', TechnicianTravelDetailView.as_view(), name='travel_detail'),
    path('travels/new/', TechnicianTravelCreateView.as_view(), name='travel_create'),
    path('travels/<int:pk>/edit/', TechnicianTravelUpdateView.as_view(), name='travel_update'),
    path('travels/<int:pk>/delete/', TechnicianTravelDeleteView.as_view(), name='travel_delete'),
    path('travels/<int:pk>/complete/', TechnicianTravelCompleteView.as_view(), name='travel_complete'),
    
    # Travel Segments
    path('travels/<int:travel_id>/segments/new/', TravelSegmentCreateView.as_view(), name='travel_segment_create'),
    path('segments/<int:pk>/edit/', TravelSegmentUpdateView.as_view(), name='travel_segment_update'),
    path('segments/<int:pk>/delete/', TravelSegmentDeleteView.as_view(), name='travel_segment_delete'),

    path('systems/', SystemListView.as_view(), name='system_list'),
    path('systems/new/', SystemCreateView.as_view(), name='system_create'),
    path('systems/<int:pk>/edit/', SystemUpdateView.as_view(), name='system_update'),
    path('systems/<int:pk>/delete/', SystemDeleteView.as_view(), name='system_delete'),

    path('users/', UserListView.as_view(), name='user_list'),
    path('users/new/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),

    # Notifications
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/monitor/', NotificationMonitorView.as_view(), name='notification_monitor'),
    path('notifications/send/', SendMessageView.as_view(), name='send_message'),
    path('notifications/<int:pk>/read/', mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', mark_all_notifications_read, name='mark_all_notifications_read'),
]
