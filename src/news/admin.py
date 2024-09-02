from django.contrib import admin
import shortuuid as uuid
from django import forms

from .models import *
# Register your models here.



class CategoryAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'description',
    )
    list_display = (
        'id',
        'name',
        'description',
    )
    search_fields = (
        'id',
        'name',
        'description',
    )

class TagAdmin(admin.ModelAdmin):
    fields = (
        'name',
    )
    list_display = (
        'id',
        'name',
    )
    search_fields = (
        'id',
        'name',
    )


class NewsAdmin(admin.ModelAdmin):
    fields = (
        'category',
        'administrative_levels',
        'projects',
        'title',
        'description',
        'total_men_present_over_35',
        'total_women_present_over_35',
        'total_people_present_over_35',
        'total_men_present_under_35',
        'total_women_present_under_35',
        'total_people_present_under_35',
        'total_people_present',
        'total_men_over_35_injured',
        'total_women_over_35_injured',
        'total_people_over_35_injured',
        'total_men_between_10_35_injured',
        'total_women_between_10_35_injured',
        'total_people_between_10_35_injured',
        'total_men_under_10_injured',
        'total_women_under_10_injured',
        'total_people_under_10_injured',
        'total_people_injured',
        'total_men_over_35_died',
        'total_women_over_35_died',
        'total_people_over_35_died',
        'total_men_between_10_35_died',
        'total_women_between_10_35_died',
        'total_people_between_10_35_died',
        'total_men_under_10_died',
        'total_women_under_10_died',
        'total_people_under_10_died',
        'total_people_died',
        'total_people_by_the_event',
        'publication_date',
        'event_date',
        'latitude',
        'longitude',
        'tags',
        'publish',
        'facilitator',
        'user',
    )
    list_display = (
        'id',
        'category',
        'title',
        'description',
        'administrative_levels',
        'projects',
        'event_date',
        'publication_date',
        'facilitator',
        'user',
        'publish',
    )
    search_fields = (
        'id',
        'category__name',
        'administrative_levels',
        'projects',
        'title',
        'description',
        'facilitator__name',
        'user_first_name',
        'user_last_name',
        'publish',
        'publication_date',
        'event_date',
    )
    raw_id_fields = (
        'category',
        'tags',
        'facilitator',
        'user',
    )

class NewsFileAdmin(admin.ModelAdmin):
    fields = (
        'news',
        'name',
        'url',
        'order',
        'principal',
        'date_taken',
        'file_type',
        'username',
        'user_email',
    )
    list_display = (
        'id',
        'name',
        'url',
        'order',
        'principal',
        'date_taken',
        'file_type',
        'username',
        'user_email',
    )
    search_fields = (
        'id',
        'news__title',
        'name',
        'url',
        'order',
        'principal',
        'date_taken',
        'file_type',
        'username',
        'user_email',
    )
    raw_id_fields = (
        'news',
    )


admin.site.register(Category, CategoryAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(News, NewsAdmin)
admin.site.register(NewsFile, NewsFileAdmin)
