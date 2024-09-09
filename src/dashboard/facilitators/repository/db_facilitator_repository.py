from django.db.models import QuerySet

from authentication.models import Facilitator
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria


class FacilitatorRepository:
    def find_by_criteria(self, criteria: FacilitatorCriteria) -> QuerySet:
        query = self.__build_query(criteria)
        return query.order_by('id')

    def __build_query(self, criteria: FacilitatorCriteria):
        query = Facilitator.objects
        if criteria.active is not None:
            query = query.filter(active=criteria.active)
        if criteria.id__in is not None:
            query = query.filter(id__in=criteria.id__in)
        if criteria.training_mode is not None:
            query = query.filter(training_mode=criteria.training_mode)
        if criteria.projects__id is not None:
            query = query.filter(projects__in=criteria.projects__id)
        if criteria.develop_mode is not None:
            query = query.filter(develop_mode=criteria.develop_mode)
        if criteria.no_sql_pass is not None:
            query = query.filter(no_sql_pass=criteria.no_sql_pass)
        if criteria.no_sql_user is not None:
            query = query.filter(no_sql_user=criteria.no_sql_user)
        return query