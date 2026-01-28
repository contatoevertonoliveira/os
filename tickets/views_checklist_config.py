
from django.views.generic import TemplateView, UpdateView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404
from django.db.models import Count
from .models import ChecklistTemplate, ChecklistTemplateItem

class ChecklistConfigView(LoginRequiredMixin, TemplateView):
    template_name = 'tickets/checklist_config.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['templates'] = ChecklistTemplate.objects.annotate(item_count=Count('items')).all()
        return context

class ChecklistTemplateCreateView(LoginRequiredMixin, CreateView):
    model = ChecklistTemplate
    fields = ['name', 'department']
    template_name = 'tickets/checklist_template_form.html'
    success_url = reverse_lazy('checklist_daily')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class ChecklistTemplateUpdateView(LoginRequiredMixin, UpdateView):
    model = ChecklistTemplate
    fields = ['name', 'department']
    template_name = 'tickets/checklist_template_form.html'
    success_url = reverse_lazy('checklist_daily')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.all().order_by('order')
        return context

class ChecklistItemCreateView(LoginRequiredMixin, CreateView):
    model = ChecklistTemplateItem
    fields = ['title', 'description', 'order']
    template_name = 'tickets/checklist_item_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        template = get_object_or_404(ChecklistTemplate, pk=self.kwargs['pk'])
        form.instance.template = template
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('checklist_template_edit', args=[self.kwargs['pk']])

class ChecklistItemDeleteView(LoginRequiredMixin, DeleteView):
    model = ChecklistTemplateItem
    template_name = 'tickets/checklist_item_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('checklist_template_edit', args=[self.object.template.id])

class ChecklistTemplateDeleteView(LoginRequiredMixin, DeleteView):
    model = ChecklistTemplate
    template_name = 'tickets/checklist_template_confirm_delete.html'
    success_url = reverse_lazy('settings')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Excluir Modelo: {self.object.name}"
        context['back_url'] = reverse_lazy('settings')
        return context
