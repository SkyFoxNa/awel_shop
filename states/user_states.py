from aiogram.fsm.state import StatesGroup, State

class ProfileEdit(StatesGroup):
    waiting_for_surname = State()
    waiting_for_name = State()
    waiting_for_phone = State()