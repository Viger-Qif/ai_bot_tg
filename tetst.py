import json

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text
)

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker
)

# =========================================
# CONFIG
# =========================================

TOKEN = "8956023974:AAGe10ZJZXD6-n9-A1F-BiExqjyP-I8V3iM"

# =========================================
# DATABASE
# =========================================

Base = declarative_base()

class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    score = Column(Integer, default=0)

    roadmap = Column(Text, default="")

    completed = Column(Text)

# =========================================
# MYSQL CONNECTION
# =========================================

engine = create_engine(
    "mysql+pymysql://u3520519_default:n8BcwTc7AcmzmO85@localhost/u3520519_default"
)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

# =========================================
# BOT
# =========================================

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# =========================================
# SAVE USER
# =========================================

def save_user(message):

    session = Session()

    tg_user = message.from_user

    print(
        f"[SAVE USER] "
        f"id={tg_user.id} "
        f"username=@{tg_user.username} "
        f"name={tg_user.full_name}"
    )

    user = session.query(User).filter_by(
        id=tg_user.id
    ).first()

    if not user:

        user = User(

            id=tg_user.id,

            score=0,

            roadmap="",

            completed=json.dumps([])

        )

        session.add(user)

        session.commit()

        print(
            f"[NEW USER CREATED] "
            f"id={tg_user.id} "
            f"username=@{tg_user.username}"
        )

    else:

        print(
            f"[USER EXISTS] "
            f"id={tg_user.id}"
        )

    session.close()

# =========================================
# START COMMAND
# =========================================

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):

    save_user(message)

    await message.answer(
        "Вы успешно зарегистрированы"
    )

# =========================================
# START
# =========================================

if __name__ == "__main__":

    print("[BOT STARTED]")

    executor.start_polling(dp)