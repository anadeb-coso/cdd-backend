import factory
from factory.django import DjangoModelFactory

from authentication.factories import FacilitatorFactory
from process_manager.models import (
    Project, Phase, Activity, Task, Cycle,
    TaskSubmission, TaskSubmissionHistory
)


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f'Project {n}')
    description = factory.Faker('paragraph')
    couch_id = factory.Sequence(lambda n: f'couch_proj_{n}')


class PhaseFactory(DjangoModelFactory):
    class Meta:
        model = Phase

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f'Phase {n}')
    order = factory.Sequence(lambda n: n)


class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity

    phase = factory.SubFactory(PhaseFactory)
    project = factory.SelfAttribute('phase.project')
    name = factory.Sequence(lambda n: f'Activity {n}')
    order = factory.Sequence(lambda n: n)
    total_tasks = 0


class CycleFactory(DjangoModelFactory):
    class Meta:
        model = Cycle

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f'Cycle {n}')
    order = factory.Sequence(lambda n: n)


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    project = factory.SubFactory(ProjectFactory)
    phase = factory.SubFactory(PhaseFactory)
    activity = factory.SubFactory(ActivityFactory)
    name = factory.Sequence(lambda n: f'Task {n}')
    order = factory.Sequence(lambda n: n)
    form = factory.Dict({"pages": []})
    attachments = factory.List([])
    capacity_attachments = factory.List([])
    couch_id = factory.Sequence(lambda n: f'couch_task_{n}')


class TaskSubmissionFactory(DjangoModelFactory):
    class Meta:
        model = TaskSubmission

    task = factory.SubFactory(TaskFactory)
    project = factory.SelfAttribute('task.project')
    cycle = factory.LazyAttribute(lambda o: o.task.cycles.first())
    administrative_level_id = factory.Sequence(lambda n: 1000 + n)
    completed = False
    form_response = factory.Dict({"q1": "Initial answer"})


class TaskSubmissionHistoryFactory(DjangoModelFactory):
    class Meta:
        model = TaskSubmissionHistory

    submission = factory.SubFactory(TaskSubmissionFactory)
    facilitator = factory.SubFactory(FacilitatorFactory)
    form_response_snapshot = factory.Dict({"q1": "Initial answer"})
    form_fields_snapshot = factory.Dict({"fields": []})
    fields_updated = factory.List(["q1"])
    intervention_type = 'update'
    page = 1
