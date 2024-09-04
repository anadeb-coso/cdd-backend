from django.db import models
from django.utils.translation import gettext_lazy as _
import os
from django.contrib.auth.models import User

from cdd.models_base import BaseModel
from authentication.models import Facilitator


class Category(BaseModel):
    name = models.CharField(max_length=100, verbose_name=_('Name'))
    description = models.TextField(verbose_name=_('Description'), null=True, blank=True)
    
    def __str__(self):
        return self.name


class Tag(BaseModel):
    name = models.CharField(max_length=255)
    
class News(BaseModel):
    category = models.ForeignKey('Category', on_delete=models.CASCADE, verbose_name=_('Category'))
    administrative_levels = models.JSONField(null=True, blank=True)
    projects = models.JSONField(null=True, blank=True)
    title = models.CharField(max_length=250, verbose_name=_('Title'))
    description = models.TextField(verbose_name=_('Description'))
    tags = models.ManyToManyField(Tag, default=[], blank=True, related_name="news_tags", verbose_name=_("Tags"))
    publish = models.BooleanField(default=False, verbose_name=_("Publish"))
    
    total_men_present_over_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total men present over 35"))
    total_women_present_over_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total women present over 35"))
    total_people_present_over_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total people present over 35"))
    total_men_present_under_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total men present under 35"))
    total_women_present_under_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total women present under 35"))
    total_people_present_under_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total people present under 35"))
    total_people_present = models.IntegerField(null=True, blank=True, verbose_name=_("Total people present"))
    
    total_men_over_35_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total men over 35 injured"))
    total_women_over_35_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total women over 35 injured"))
    total_people_over_35_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total people over 35 injured"))
    total_men_between_10_35_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total men between 10 and 35 injured"))
    total_women_between_10_35_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total women between 10 and 35 injured"))
    total_people_between_10_35_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total people between 10 and 35 injured"))
    total_men_under_10_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total men under 10 injured"))
    total_women_under_10_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total women under 10 injured"))
    total_people_under_10_injured = models.IntegerField(null=True, blank=True, verbose_name=_("Total people under 10 injured"))
    total_people_injured  = models.IntegerField(null=True, blank=True, verbose_name=_("Total people injured"))
    
    total_men_over_35_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total men over 35 died"))
    total_women_over_35_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total women over 35 died"))
    total_people_over_35_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total people over 35 died"))
    total_men_between_10_35_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total men between 10 and 35 died"))
    total_women_between_10_35_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total women between 10 and 35 died"))
    total_people_between_10_35_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total people between 10 and 35 died"))
    total_men_under_10_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total men under 10 died"))
    total_women_under_10_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total women under 10 died"))
    total_people_under_10_died = models.IntegerField(null=True, blank=True, verbose_name=_("Total people under 10 died"))
    total_people_died  = models.IntegerField(null=True, blank=True, verbose_name=_("Total people died"))
    
    total_people_by_the_event  = models.IntegerField(null=True, blank=True, verbose_name=_("Total people affected by the event"))

    publication_date = models.DateTimeField(blank=True, null=True, verbose_name=_("Publication date"))
    event_date = models.DateField(blank=True, null=True, verbose_name=_("Event date"))
    
    
    latitude = models.FloatField(null=True, blank=True, verbose_name=_("Latitude"))
    longitude = models.FloatField(null=True, blank=True, verbose_name=_("Longitude"))

    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('Facilitator'))
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('User'))
    
    def __str__(self):
        return f"{self.title}"

    def get_files(self):
        return self.newsfile_set.get_queryset().order_by("-date_taken")
    
    def get_file(self):
        file = self.newsfile_set.get_queryset().filter(principal=True).first()
        if not file:
            file = self.newsfile_set.get_queryset().first()
        return file
    
    # def save(self, *args, **kwargs):
    #     super().save(*args, **kwargs)
    #     return super().save(*args, **kwargs)


class NewsFile(BaseModel):
    news = models.ForeignKey(News, null=True, blank=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    principal = models.BooleanField(default=False)
    date_taken = models.DateField()
    file_type = models.CharField(max_length=100, default="image")
    username = models.CharField(max_length=255)
    user_email = models.CharField(max_length=255, null=True, blank=True)



class Subscription(BaseModel):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
