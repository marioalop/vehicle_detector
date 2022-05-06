from mongoengine import connect, Document, DynamicDocument, StringField, IntField, DateTimeField, DictField, ListField, BooleanField
from datetime import datetime
import os
from typing import Any
import json


connect(host=os.getenv('MONGODB_URL'))


class Vehicle(Document):
    year = IntField()
    make = StringField()
    model = StringField()
    category = StringField()
    created = DateTimeField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.created:
            self.created = datetime.now()
        return super(Vehicle, self).save(*args, **kwargs)
    
    def serialize(self):
        data = self.to_mongo().to_dict()
        data['_id'] = str(data['_id'])
        data['created'] = str(data['created'])
        return data
    