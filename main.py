import logging

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import Message, ContentTypes, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, \
    ReplyKeyboardRemove
from aiogram.utils import executor

from database import db, Person, Admin

TOKEN = "PASTE TOKEN HERE"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

logging.basicConfig(#filename="bot.log",
                    format='%(asctime)s: %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
                    level=logging.INFO)


class Registration(StatesGroup):
    get_code = State()


class PeopleChose(StatesGroup):
    people = State()


@dp.message_handler(commands=['start'])
async def starter(message: Message):
    chat_id = message.chat.id
    person = Person.get_or_none(Person.chat_id == chat_id)
    if person is not None:
        await message.answer(text="Already registered")
    else:
        await Registration.get_code.set()
        await message.answer(text="Send code word")


@dp.message_handler(state=Registration.get_code, content_types=ContentTypes.TEXT)
async def get_code(message: Message, state: FSMContext):
    person = Person.get_or_none(
        (Person.code_word == str(message.text)) & (Person.chat_id.is_null())
    )
    if person is not None:
        person.chat_id = message.chat.id
        person.save()
        await state.finish()
        await message.answer(text="Registered, wait for notifications")
    else:
        async with state.proxy() as data:
            if 'get_code' in data.keys():
                if data['get_code'] > 2:
                    await message.answer(text="Too many attempts")
                    return
                else:
                    data['get_code'] += 1
            else:
                data['get_code'] = 1
        await message.answer(text=f"No such code word or chat is already registered {data['get_code']}")


@dp.message_handler()
async def main_handler(message: Message):
    logging.info(message)
    chat_id = message.chat.id
    admin = Admin.get_or_none(Admin.chat_id == chat_id)
    if admin is not None:
        await message.answer(
            text='Choose people',
            reply_markup=get_person_choose_keyboard()
        )
        await PeopleChose.people.set()
    else:
        await message.answer(text='Just wait for notifications')


@dp.callback_query_handler(lambda call: call.data == 'send', state=PeopleChose.people)
async def send_notifications(call: CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        already_in_list = data['people']
    await state.finish()
    for chat_id in already_in_list:
        await bot.send_message(
            chat_id=chat_id, text=f"Notification for {chat_id} person",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Read", callback_data=f"read:{call.message.chat.id}")]], one_time_keyboard=True)
        )
    await call.message.edit_text(text="Notifications sent")


@dp.callback_query_handler(lambda call: call.data.split(":")[0] == 'read')
async def send_notifications(call: CallbackQuery):
    spl = call.data.split(':')
    admin_chat_id = spl[1]
    person_chat_id = call.message.chat.id
    person = Person.get_or_none(Person.chat_id == person_chat_id)
    message_text = call.message.text
    await bot.send_message(
        chat_id=admin_chat_id, text=f"User {person.name} just approved reading next message:\n\"{message_text}\"",
    )
    await call.message.delete_reply_markup()


@dp.callback_query_handler(state=PeopleChose.people)
async def choose_person(call: CallbackQuery, state: FSMContext):
    spl = call.data.split(':')
    person_chat_id = spl[0]
    person_name = spl[1]
    async with state.proxy() as data:
        if 'people' in data.keys():
            data['people'].append(person_chat_id)
        else:
            data['people'] = [person_chat_id]
        already_in_list = data['people']
    await call.message.edit_text(
        text=f"{call.message.text}\n{person_name}",
        reply_markup=get_person_choose_keyboard(ignore_ids=already_in_list)
    )


def get_person_choose_keyboard(ignore_ids=None):
    if ignore_ids is None:
        ignore_ids = []
    buttons = [[InlineKeyboardButton(text=person.name, callback_data=f"{person.chat_id}:{person.name}")] for person in Person.select().where(Person.chat_id.not_in(ignore_ids))]
    buttons += [[InlineKeyboardButton(text="Send", callback_data="send")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons, one_time_keyboard=True)


async def on_startup(dispatcher: Dispatcher):
    db.close()
    db.create_tables([Person, Admin])


async def shutdown(dispatcher: Dispatcher):
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    db.close()

if __name__ == "__main__":
    logging.info("BOT STARTED")
    executor.start_polling(dispatcher=dp, on_startup=on_startup, on_shutdown=shutdown)
