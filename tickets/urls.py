from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    DashboardView, TicketListView, TicketCreateView, TicketUpdateView, TicketDeleteView, TicketDetailView, TicketModalView, TokenLoginView,
    ClientListView, ClientCreateView, ClientUpdateView, ClientDeleteView,
    EquipmentListView, EquipmentCreateView, EquipmentUpdateView, EquipmentDeleteView,
    OrderTypeListView, OrderTypeCreateView, OrderTypeUpdateView, OrderTypeDeleteView,
    ProblemTypeListView, ProblemTypeCreateView, ProblemTypeUpdateView, ProblemTypeDeleteView,
    TechnicianListView, TechnicianCreateView, TechnicianUpdateView, TechnicianDeleteView,
    SystemListView, SystemCreateView, SystemUpdateView, SystemDeleteView,
    ProfileView, SettingsView,
    TaskListView, TaskFavoriteView
)

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    
    # Tasks
    path('tasks/', TaskListView.as_view(), name='task_list'),
    path('tasks/<int:pk>/favorite/', TaskFavoriteView.as_view(), name='task_favorite'),
    
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

    # Cadastros
    path('clients/', ClientListView.as_view(), name='client_list'),
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

    path('systems/', SystemListView.as_view(), name='system_list'),
    path('systems/new/', SystemCreateView.as_view(), name='system_create'),
    path('systems/<int:pk>/edit/', SystemUpdateView.as_view(), name='system_update'),
    path('systems/<int:pk>/delete/', SystemDeleteView.as_view(), name='system_delete'),
]
