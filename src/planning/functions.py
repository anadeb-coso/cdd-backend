
from django.contrib.auth.models import User, Group
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
import pytz
import os
import pandas as pd
from sys import platform

from planning.models import Activity, ActivityDeadline
from authentication.models import Facilitator
from process_manager.models import Project



def alert_users(project_name="COSO"):
    project = Project.objects.filter(name=project_name).first()
    deadlines = ActivityDeadline.objects.filter(project_id=project.id)
    datas = {
        _("Name"): {},
        _("Username"): {},
        _("Email"): {},
        _("Monday"): {},
        _("Tuesday"): {},
        _("Wednesday"): {},
        _("Thursday"): {},
        _("Friday"): {},
        _("Saturday"): {},
        _("Sunday"): {},
        _("All"): {},
    }
    DAYS = [
        _("Monday"),
        _("Tuesday"),
        _("Wednesday"),
        _("Thursday"),
        _("Friday"),
        _("Saturday"),
        _("Sunday"),
    ]
    print()
    all_activities_ids = []
    for deadline in deadlines:
        print(deadline)
        activities = []
        today = datetime.today()
        week_day = today.weekday()
        hour = f"0{today.hour}" if today.hour <= 9 else f"{today.hour}"
        minute = f"0{today.minute}" if today.minute <= 9 else f"{today.minute}"
        hour_minute = f"{hour}:{minute}"
        
        if (deadline.day == week_day and deadline.hour <= hour_minute) or (deadline.day < week_day):
            monday = today - timedelta(days=week_day)
            begin_plan_day = monday + timedelta(days=(deadline.day+1))
            
            next_seven_dates = [(begin_plan_day + timedelta(days=i)).date() for i in range(7)]
            next_seven_datetime_list = [parse_datetime(f"{d.strftime('%Y-%m-%d')}T00:00:00.000000Z").replace(tzinfo=pytz.UTC) for d in next_seven_dates]
            
            planned_datetime_list_query = Q()
            for _date in next_seven_datetime_list:
                planned_datetime_list_query |= (Q(planned_datetime_start__lte=_date) & Q(planned_datetime_end__gte=_date))
                

            groups = deadline.activities_deadline_groups.all()
            users = User.objects.filter(groups__in=list(groups))
            facilitators = []
            if groups.filter(name="Facilitatot").exists():
                facilitators = Facilitator.objects.filter(develop_mode=False, training_mode=False, projects__in=[project.id])
            print(users)
            print(facilitators)
            users_facilitators = list(users) + list(facilitators)
            
            activities = Activity.objects.filter(
                Q(planned_date__in=next_seven_dates) | Q(Q(type="vacation") & planned_datetime_list_query), 
                Q(user__in=users) | Q(facilitator__in=facilitators), 
                project_id=project.id
            )

            activities = activities.exclude(id__in=all_activities_ids)
            count = 0
            for u_f in users_facilitators:
                user_full_name =  u_f.name if hasattr(u_f, 'no_sql_user') else f"{u_f.last_name} {u_f.first_name}"
                user_email = u_f.email
                user_username = u_f.username
                datas[_("Name")][count] = user_full_name
                datas[_("Username")][count] = user_username
                datas[_("Email")][count] = user_email

                if hasattr(u_f, 'no_sql_user'):
                    activities_user = activities.filter(facilitator=u_f)
                else:
                    activities_user = activities.filter(user=u_f)

                if not activities_user.exists():
                    datas[_("Monday")][count] = _("No")
                    datas[_("Tuesday")][count] = _("No")
                    datas[_("Wednesday")][count] = _("No")
                    datas[_("Thursday")][count] = _("No")
                    datas[_("Friday")][count] = _("No")
                    datas[_("Saturday")][count] = _("No")
                    datas[_("Sunday")][count] = _("No")
                    datas[_("All")][count] = _("No")
                else:
                    _day_count = 0
                    datas[_("All")][count] = _("No")
                    have_plan = False
                    for _day in next_seven_dates:
                        _week_day = _day.weekday()
                        if not activities_user.filter(
                            Q(planned_datetime_start__lte=next_seven_datetime_list[_day_count]) & Q(planned_datetime_end__gte=next_seven_datetime_list[_day_count])
                            ).exists():
                            if not activities_user.filter(planned_date=_day).exists():
                                datas[DAYS[_week_day]][count] = _("No")
                            else:
                                datas[DAYS[_week_day]][count] = _("Yes")
                                have_plan = True
                        else:
                            datas[DAYS[_week_day]][count] = _("Yes")
                            have_plan = True

                        _day_count += 1

                    if have_plan:
                        datas[_("All")][count] = _("Yes")

                count += 1

        

            # for a in activities:
            #     user = a.user if a.user else (a.facilitator if a.facilitator else None)
            #     user_full_name = f"{a.user.last_name} {a.user.first_name}" if a.user else (a.facilitator.name if a.facilitator else None)
            #     user_email = a.user.email if a.user else (a.facilitator.email if a.facilitator else None)
            #     user_username = a.user.username if a.user else (a.facilitator.username if a.facilitator else None)
            #     if user_username:
            #         if datas.get(user_username):
            #             pass
            #         else:
            #             datas[user_username] = {
            #                 'user_name': user_full_name,
            #                 'user_email': user_email,
            #                 'user_username': user_username,

            #             }

            all_activities_ids += [a.id for a in activities]


    
    if not os.path.exists("media/statistics"):
            os.makedirs("media/statistics")
    file_path = f'statistics/planning_{str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_")}.xlsx'

    df = pd.DataFrame(datas).to_excel("media/"+file_path, sheet_name='Planning Situation', index=False)

    # with pd.ExcelWriter("media/"+file_path) as writer:
    #     df.to_excel(writer, sheet_name='Planning Situation', index=False)
        
        # for k, v in datas_dict_planning.items():
        #     if k != 'Précédentes':
        #         pd.DataFrame(
        #             v
        #         ).to_excel(writer, sheet_name=k, index=False)

        
    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path