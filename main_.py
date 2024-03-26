import logging  # логирование действий бота
import asyncio  # функционирование бота
import sys  # работа с системой
import json  # работа с JSON файлами
import pathlib  # работа с файловой системой
import matplotlib.pyplot as plt
import numpy as np

from random import randrange
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import types
from aiogram.types import FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession


session = AiohttpSession(proxy='http://proxy.server:3128')
bot = Bot(token="6834250266:AAHTcW7ayKq4gjwt9hIrrrJ8KfUFOPsWArg", session=session)
form_router = Router()
learn_data = json.loads(pathlib.Path("ru.json").read_text(encoding="UTF8"))
users = {}


class Form(StatesGroup):
    select_module = State()
    select_type = State()
    select_chapter = State()
    select_start = State()


@form_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Form.select_module)
    await message.answer("/start — начало работы бота\n" +
                        "/about — о боте\n" +
                        "/help — инструкция по работе с ботом\n" +
                        "/reset — сбросить всю свою статистику\n" +
                        "/stat — получить статистику по текущему пользователю\n" +
                         "Выберите раздел для изучения:", reply_markup=markup(learn_data.keys()))


@form_router.message(Command('help'))
async def cmd_help(message: types.Message) -> None:
    await message.answer("/start — начало работы бота\n" +
                        "/about — о боте\n" +
                        "/help — инструкция по работе с ботом\n" +
                        "/reset — сбросить всю свою статистику\n" +
                        "/stat — получить статистику по текущему пользователю\n")


@form_router.message(Command('about'))
async def cmd_about(message: types.Message) -> None:
    await message.answer("Данный бот разработан Спесивцевой Софьей\n" +
                        "студенткой НИУ ВШЭ Группа: БКЛ223\n" +
                         "Предназначен для проверки знаний по русскому языку")


@form_router.message(Command('reset'))
async def cmd_reset(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Form.select_module)
    await message.answer("Ваша статистика сброшена\nВыберите раздел для изучения:",
                         reply_markup=markup(learn_data.keys()))


@form_router.message(Command('stat'))
async def cmd_stat(message: types.Message, state: FSMContext) -> None:
    message_data = await state.get_data()
    categories = list(message_data["questions"].keys())
    a = message_data["questions"]
    scores = [sum([a[i][j] for j in list(a[i].keys())]) for i in categories]
    lost_scores = [sum([1 for j in list(a[i].keys()) if a[i][j] == 0]) for i in categories]

    width = 0.35
    ind = np.arange(len(categories))
    p1 = plt.bar(ind, scores, width, color='skyblue')
    p2 = plt.bar(ind, lost_scores, width, bottom=scores, color='lightcoral')

    plt.xticks(ind, categories)
    plt.legend((p1[0], p2[0]), ('Верно', 'Неверно'))
    plt.xlabel('Разделы')
    plt.ylabel('Баллы')
    plt.title(f'Баллы по разделам пользователя "{message.from_user.full_name}"')

    rand = randrange(10000)
    file_name = f'foo{rand}.png'
    plt.savefig(file_name)
    photo_bot = FSInputFile(pathlib.Path(file_name).absolute())
    await bot.send_photo(message.from_user.id, photo_bot, caption=f"Ваша статистика")
    pathlib.Path(file_name).unlink()


@form_router.message(Form.select_module)
@form_router.message(Form.select_type, F.text.casefold() == "нет")
async def select_module(message: types.Message, state: FSMContext) -> None:
    if message.text.casefold() != "нет":
        await state.update_data(modul=message.text)
    message_data = await state.get_data()
    await message.answer(f"Вы выбрали раздел {message_data['modul']}.\nКакой формат выберите?",
                         reply_markup=markup(["Тест", "Рейтинг"]))
    await state.set_state(Form.select_type)


@form_router.message(Form.select_type)
async def select_type(message: types.Message, state: FSMContext) -> None:
    await state.update_data(type=message.text.casefold())
    answer_text = "Вы выбрали формат "
    if message.text.casefold() == "тест":
        answer_text += "Теста\nПосле каждого своего ответа вы узнаете приавльной он или нет. "
    else:
        answer_text += "Рейтинга\nВам необходимо решить 15 заданий, после чего вы узнаете свой балл. "
    await message.answer(answer_text + "\nГотовы?",
                         reply_markup=markup(["Да", "Нет"]))
    await state.set_state(Form.select_start)


@form_router.message(Form.select_start)
async def select_start(message: types.Message, state: FSMContext) -> None:
    if message.text.casefold() == "да":
        message_data = await state.get_data()
        modul = learn_data[message_data['modul']]
        await state.update_data(task_type=modul["task_type"])

    message_data = await state.get_data()
    if "questions" in list(message_data.keys()) and message.text.casefold() not in ["да", "нет"]:
        await check_answer(message, state, message_data["type"] == 'тест')

    await send_question(message, state)


async def check_answer(message: types.Message, state: FSMContext, send_message: bool):
    message_data = await state.get_data()
    tasks = message_data["questions"].get(message_data['modul'])
    last_task = list(tasks.keys())[list(tasks.values()).index(-1)]

    modul = learn_data[message_data['modul']]

    answer_index = str(next((index for (index, d) in enumerate(modul[last_task]["answers"]) if d["text"] == message.text), None))
    answer_correct = False
    if answer_index != "None":
        answer_correct = modul[last_task]["answers"][int(answer_index)]["correct"]

    stat = {"total": 0, "correct": 0}
    if "stat" in list(message_data.keys()):
        stat = message_data["stat"]
    stat["total"] += 1
    if answer_correct:
        stat["correct"] += 1
    questions = message_data["questions"]
    questions[message_data['modul']][last_task] = 1 if answer_correct else 0
    await state.update_data(questions=questions)
    await state.update_data(stat=stat)

    if send_message:
        await bot.send_message(message.from_user.id, "Верно" if answer_correct else "Неверно")


async def send_stat(message: types.Message, state: FSMContext):
    message_data = await state.get_data()
    tasks = message_data["stat"]
    all_tasts = tasks["total"]
    correct = tasks["correct"]
    image = "good.jpg" if correct / all_tasts >= 0.5 else "bad.jpg"
    photo_bot = FSInputFile(pathlib.Path(image).absolute())
    await bot.send_photo(message.from_user.id, photo_bot, caption=f"Вы решили верно {correct} из {all_tasts} задач")


async def send_question(message: types.Message, state: FSMContext) -> None:
    message_data = await state.get_data()
    modul = learn_data[get_user_data(message_data, 'modul')]
    task_size = len(modul) - 1

    if "questions" in list(message_data.keys()):
        questions_in_module = get_user_data(message_data, 'questions', get_user_data(message_data, 'modul'))
        if questions_in_module:
            question_modle_len = len(questions_in_module)
        else:
            question_modle_len = 0

        task_number = get_task_number(task_size, list(message_data["questions"].keys())) \
            if (task_size > question_modle_len and question_modle_len < 16) else "0"
    else:
        task_number = randrange(task_size) + 1

    if task_number == "0":
        await send_stat(message, state)
        await state.set_state(Form.select_module)
        await message.answer("Задания закончились.\nВыберите раздел для изучения:",
                             reply_markup=markup(learn_data.keys()))
    else:
        task = modul[str(task_number)]

        if "questions" in list(message_data.keys()):
            modul_questions = message_data["questions"]
            if message_data['modul'] in message_data["questions"]:
                modul_questions[message_data['modul']][str(task_number)] = -1
            else:
                modul_questions[message_data['modul']] = {str(task_number): -1}
        else:
            modul_questions = {message_data['modul']: {str(task_number): -1}}

        await state.update_data(questions=modul_questions)
        await message.answer(task["question"], reply_markup=get_task_buttons(message_data['task_type'], task))


def get_user_data(user_data: dict, *args):
    result = user_data
    for arg in args:
        if arg in list(result.keys()):
            result = result.get(arg)
        else:
            result = None
            break
    return result


def get_task_buttons(task_type: str, task: dict) -> types.ReplyKeyboardMarkup:
    buttons = []
    if task_type == "button":
        buttons = [i["text"] for i in task["answers"]]
    return markup(buttons)


def get_task_number(task_size: int, ignore: list) -> str:
    task_number = str(randrange(task_size) + 1)
    while task_number in ignore:
        task_number = str(randrange(task_size) + 1)
    return task_number


def markup(buttons: list = None) -> types.ReplyKeyboardMarkup:
    if buttons:
        keyboards = [types.KeyboardButton(text=i) for i in buttons]
        result = types.ReplyKeyboardMarkup(keyboard=[keyboards], resize_keyboard=True)
    else:
        result = types.ReplyKeyboardRemove()
    return result


async def main():
    dp = Dispatcher()
    dp.include_router(form_router)

    await dp.start_polling(bot, storage=MemoryStorage())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
