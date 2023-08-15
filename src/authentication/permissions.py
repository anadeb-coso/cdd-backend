from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.defaults import page_not_found
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group

"""
All Groups permissions
    - SuperAdmin            : 
    - CDD Specialist        : CDDSpecialist
    - Admin                 : Admin
    - Evaluator             : Evaluator
    - Accountant            : Accountant
    - Regional Coordinator  : RegionalCoordinator
    - National Coordinator  : NationalCoordinator
    - General Manager  : GeneralManager
    - Director  : Director
    - Advisor  : Advisor
    - Minister  : Minister
"""


class SuperAdminPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            return True
        return False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(SuperAdminPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class AdminPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="Admin").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(AdminPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class CDDSpecialistPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="CDDSpecialist").exists()
            or 
            self.request.user.groups.filter(name="Evaluator").exists()
            or 
            self.request.user.groups.filter(name="Admin").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
                
        # if self.request.user.is_authenticated and self.request.user.has_perm('authentication.view_facilitator'):
        #     return True
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(CDDSpecialistPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class EvaluatorPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="Evaluator").exists()
            or 
            self.request.user.groups.filter(name="Admin").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(EvaluatorPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class AccountantPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="Accountant").exists()
            or 
            self.request.user.groups.filter(name="Admin").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(AccountantPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)
    

class RegionalCoordinatorPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="RegionalCoordinator").exists()
            or 
            self.request.user.groups.filter(name="Admin").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(RegionalCoordinatorPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class NationalCoordinatorPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="NationalCoordinator").exists()
            or 
            self.request.user.groups.filter(name="Admin").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(NationalCoordinatorPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)



class GeneralManagerPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="GeneralManager").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(GeneralManagerPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class DirectorPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="Director").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(DirectorPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)
    

class AdvisorPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="Advisor").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(AdvisorPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)
    


class MinisterPermissionRequiredMixin(UserPassesTestMixin):
    permission_required = None

    def test_func(self):
        return True if(self.request.user.is_authenticated and (
            self.request.user.groups.filter(name="Minister").exists()
            or 
            bool(self.request.user.is_superuser)
        )) else False
    
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return page_not_found(self.request, _('Page not found').__str__())
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        return super(MinisterPermissionRequiredMixin, self).dispatch(request, *args, **kwargs)