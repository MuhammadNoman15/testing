from django.db import models

# Create your models here.

class Item(models.Model):
    date = models.DateField()  # Add this line

    def __str__(self):
        return self.name