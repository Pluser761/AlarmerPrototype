from peewee import *

db = SqliteDatabase('alarm.db')


class Person(Model):
    name = CharField()
    code_word = CharField()
    chat_id = CharField(null=True)

    class Meta:
        database = db


class Admin(Model):
    chat_id = CharField()

    class Meta:
        database = db
