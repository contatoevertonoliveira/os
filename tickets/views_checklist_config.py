
from django.views.generic import TemplateView, UpdateView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Count
from django.db import transaction
from .models import ChecklistTemplate, ChecklistTemplateItem
from .forms import ChecklistTemplateForm, ChecklistTemplateItemForm, ChecklistTemplateItemOptionFormSet

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
    form_class = ChecklistTemplateForm
    template_name = 'tickets/checklist_template_form.html'

    def get_success_url(self):
        return reverse('checklist_template_edit', args=[self.object.id])

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class ChecklistTemplateUpdateView(LoginRequiredMixin, UpdateView):
    model = ChecklistTemplate
    form_class = ChecklistTemplateForm
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
        context['items'] = self.object.items.all().order_by('order', 'id').annotate(options_count=Count('options'))
        return context

class ChecklistItemCreateView(LoginRequiredMixin, CreateView):
    model = ChecklistTemplateItem
    form_class = ChecklistTemplateItemForm
    template_name = 'tickets/checklist_item_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = get_object_or_404(ChecklistTemplate, pk=self.kwargs['pk'])
        context['template'] = template
        if self.request.POST:
            context['options_formset'] = ChecklistTemplateItemOptionFormSet(self.request.POST, prefix='opts')
        else:
            context['options_formset'] = ChecklistTemplateItemOptionFormSet(prefix='opts')
        return context

    def post(self, request, *args, **kwargs):
        template = get_object_or_404(ChecklistTemplate, pk=self.kwargs['pk'])
        form = self.get_form()
        options_formset = ChecklistTemplateItemOptionFormSet(request.POST, prefix='opts')
        if form.is_valid() and options_formset.is_valid():
            with transaction.atomic():
                item = form.save(commit=False)
                item.template = template
                item.save()
                options_formset.instance = item
                options_formset.save()
            return redirect('checklist_template_edit', template.id)
        return self.render_to_response(self.get_context_data(form=form, options_formset=options_formset))

    def get_success_url(self):
        return reverse('checklist_template_edit', args=[self.kwargs['pk']])

class ChecklistItemUpdateView(LoginRequiredMixin, UpdateView):
    model = ChecklistTemplateItem
    form_class = ChecklistTemplateItemForm
    template_name = 'tickets/checklist_item_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template'] = self.object.template
        if self.request.POST:
            context['options_formset'] = ChecklistTemplateItemOptionFormSet(self.request.POST, instance=self.object, prefix='opts')
        else:
            context['options_formset'] = ChecklistTemplateItemOptionFormSet(instance=self.object, prefix='opts')
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        options_formset = ChecklistTemplateItemOptionFormSet(request.POST, instance=self.object, prefix='opts')
        if form.is_valid() and options_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                options_formset.save()
            return redirect('checklist_template_edit', self.object.template.id)
        return self.render_to_response(self.get_context_data(form=form, options_formset=options_formset))

    def get_success_url(self):
        return reverse('checklist_template_edit', args=[self.object.template.id])

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
