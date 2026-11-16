import os
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand,CommandError
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        if len(os.getenv('SECRET_KEY',''))<32: raise CommandError('SECRET_KEY must be configured with at least 32 characters')
        name=os.getenv('ADMIN_USERNAME','admin'); password=os.getenv('ADMIN_PASSWORD','')
        if User.objects.filter(username=name).exists(): return
        if len(password)<16: raise CommandError('ADMIN_PASSWORD must have at least 16 characters')
        User.objects.create_user(name,password=password,is_staff=True,is_superuser=True)
        self.stdout.write('Administrator created (password not logged)')
