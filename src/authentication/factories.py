import factory
from factory.django import DjangoModelFactory

from authentication.models import Facilitator, User


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances for testing."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        password = extracted or 'defaultpass123'
        self.set_password(password)
        self.save()


class FacilitatorFactory(DjangoModelFactory):
    """Factory for creating Facilitator instances."""

    class Meta:
        model = Facilitator

    user = factory.SubFactory(UserFactory)
