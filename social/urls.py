from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # Follows
    path('follow/<str:username>/',            views.toggle_follow,  name='toggle_follow'),
    path('u/<str:username>/<str:mode>/',      views.follow_list,    name='follow_list'),

    # Chat
    path('messages/',                         views.inbox,                name='inbox'),
    path('messages/with/<str:username>/',     views.start_conversation,   name='start_conversation'),
    path('messages/<int:pk>/',                views.conversation_detail,  name='conversation'),
    path('messages/<int:pk>/send/',           views.send_message,         name='send_message'),
    path('messages/<int:pk>/fetch/',          views.fetch_messages,       name='fetch_messages'),

    path('notifications/',                  views.notifications_view,         name='notifications'),
    path('notifications/<int:pk>/open/',    views.notification_open,          name='notification_open'),
    path('notifications/read-all/',         views.notifications_read_all,     name='notifications_read_all'),
    path('notifications/unread-count/',     views.notifications_unread_count, name='notifications_unread_count'),
]

