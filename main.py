#!/usr/bin/env python3
from __future__ import annotations
from collections import UserDict
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple, Iterable
from abc import ABC, abstractmethod
import functools
import pickle
import shlex

class Field:
    def __init__(self, value: str):
        self.value = value
    def __str__(self) -> str:
        return str(self.value)

class Name(Field):
    pass

class Phone(Field):
    def __init__(self, value: str):
        raw = value.strip()
        if not (raw.isdigit() and len(raw) == 10):
            raise ValueError("Номер телефону має складатися рівно з 10 цифр.")
        super().__init__(raw)

class Birthday(Field):
    def __init__(self, value: str):
        try:
            dt = datetime.strptime(value.strip(), "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Invalid date format. Use DD.MM.YYYY")
        super().__init__(dt.strftime("%d.%m.%Y"))

class Record:
    def __init__(self, name: str):
        self.name = Name(name)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None
    def add_phone(self, phone: str) -> None:
        p = Phone(phone)
        if any(ph.value == p.value for ph in self.phones):
            return
        self.phones.append(p)
    def remove_phone(self, phone: str) -> None:
        cleaned = Phone(phone).value
        for i, ph in enumerate(self.phones):
            if ph.value == cleaned:
                del self.phones[i]
                return
        raise ValueError("Цього номеру немає у контакті.")
    def edit_phone(self, old: str, new: str) -> None:
        old_clean = Phone(old).value
        new_phone = Phone(new)
        for ph in self.phones:
            if ph.value == old_clean:
                ph.value = new_phone.value
                return
        raise ValueError("Старий номер не знайдено у контакті.")
    def add_birthday(self, bday: str) -> None:
        if self.birthday is not None:
            raise ValueError("День народження вже задано для цього контакту.")
        self.birthday = Birthday(bday)

class AddressBook(UserDict):
    def _key(self, name: str) -> str:
        return name.casefold()
    def add_record(self, record: Record) -> None:
        self.data[self._key(record.name.value)] = record
    def find(self, name: str) -> Optional[Record]:
        return self.data.get(self._key(name))
    def delete(self, name: str) -> None:
        key = self._key(name)
        if key in self.data:
            del self.data[key]
        else:
            raise KeyError("Контакт з таким іменем не знайдено.")
    @staticmethod
    def _shift_if_weekend(d: date) -> date:
        if d.weekday() == 5:
            return d + timedelta(days=2)
        if d.weekday() == 6:
            return d + timedelta(days=1)
        return d
    def get_upcoming_birthdays(self, days: int = 7) -> List[Dict[str, str]]:
        today = date.today()
        end_date = today + timedelta(days=days - 1)
        result: List[Dict[str, str]] = []
        for rec in self.data.values():
            if not rec.birthday:
                continue
            bday = datetime.strptime(rec.birthday.value, "%d.%m.%Y").date()
            bday_this_year = bday.replace(year=today.year)
            if bday_this_year < today:
                bday_this_year = bday_this_year.replace(year=today.year + 1)
            greet = self._shift_if_weekend(bday_this_year)
            if today <= greet <= end_date:
                result.append({"name": rec.name.value, "date": greet.strftime("%d.%m.%Y")})
        result.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date())
        return result

DEFAULT_DB = "addressbook.pkl"

def save_data(book: AddressBook, filename: str = DEFAULT_DB) -> None:
    with open(filename, "wb") as f:
        pickle.dump(book, f, protocol=pickle.HIGHEST_PROTOCOL)

def load_data(filename: str = DEFAULT_DB) -> AddressBook:
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return AddressBook()

class BaseView(ABC):
    @abstractmethod
    def show_welcome(self) -> None: ...
    @abstractmethod
    def show_goodbye(self) -> None: ...
    @abstractmethod
    def show_message(self, text: str) -> None: ...
    @abstractmethod
    def show_error(self, text: str) -> None: ...
    @abstractmethod
    def show_contact(self, rec: Record) -> None: ...
    @abstractmethod
    def show_contacts(self, recs: Iterable[Record]) -> None: ...
    @abstractmethod
    def show_birthdays(self, items: List[Dict[str, str]]) -> None: ...
    @abstractmethod
    def show_help(self, commands: Dict[str, str]) -> None: ...

class ConsoleView(BaseView):
    def show_welcome(self) -> None:
        print("Welcome to the assistant bot!")
    def show_goodbye(self) -> None:
        print("Good bye!")
    def show_message(self, text: str) -> None:
        print(text)
    def show_error(self, text: str) -> None:
        print(f"[ERROR] {text}")
    def show_contact(self, rec: Record) -> None:
        phones = ", ".join(ph.value for ph in rec.phones) if rec.phones else "—"
        bday = rec.birthday.value if rec.birthday else "—"
        print(f"{rec.name.value}: phones [{phones}] | birthday [{bday}]")
    def show_contacts(self, recs: Iterable[Record]) -> None:
        empty = True
        for rec in recs:
            empty = False
            self.show_contact(rec)
        if empty:
            print("Адресна книга порожня.")
    def show_birthdays(self, items: List[Dict[str, str]]) -> None:
        if not items:
            print("Найближчими 7 днями іменин немає.")
            return
        for it in items:
            d = it["date"]
            weekday = datetime.strptime(d, "%d.%m.%Y").strftime("%A")
            print(f"{d} ({weekday}): {it['name']}")
    def show_help(self, commands: Dict[str, str]) -> None:
        print("Доступні команди:")
        for cmd, desc in commands.items():
            print(f"  {cmd:<22} {desc}")

def input_error(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except IndexError:
            self.view.show_error("Недостатньо аргументів.")
        except AttributeError:
            self.view.show_error("Контакт не знайдено.")
        except KeyError as e:
            self.view.show_error(str(e) if str(e) else "Не знайдено.")
        except ValueError as e:
            self.view.show_error(str(e))
        except Exception as e:
            self.view.show_error(f"Сталася помилка: {e}")
    return wrapper

class App:
    def __init__(self, book: AddressBook, view: BaseView):
        self.book = book
        self.view = view
        self.commands_help: Dict[str, str] = {
            "hello": "Привітання",
            "help": "Показати довідку",
            "add <name> <phone>": "Додати контакт або телефон (10 цифр)",
            "change <name> <old> <new>": "Замінити номер у контакті",
            "remove-phone <name> <phone>": "Видалити номер у контакті",
            "delete <name>": "Видалити контакт",
            "phone <name>": "Показати контакти/телефони",
            "all": "Показати всі контакти",
            "add-birthday <name> <DD.MM.YYYY>": "Додати ДН",
            "show-birthday <name>": "Показати ДН",
            "birthdays": "Найближчі привітання (7 днів)",
            "exit | close": "Вихід"
        }
    @staticmethod
    def parse_input(line: str) -> Tuple[str, List[str]]:
        parts = shlex.split(line.strip())
        if not parts:
            return "", []
        return parts[0].lower(), parts[1:]
    def autosave(self):
        save_data(self.book, DEFAULT_DB)
    @input_error
    def handle_add(self, args: List[str]):
        name, phone, *_ = args
        rec = self.book.find(name)
        if rec is None:
            rec = Record(name)
            self.book.add_record(rec)
            msg = "Contact added."
        else:
            msg = "Contact updated."
        rec.add_phone(phone)
        self.autosave()
        self.view.show_message(msg)
    @input_error
    def handle_change(self, args: List[str]):
        name, old_p, new_p, *_ = args
        rec = self.book.find(name)
        rec.edit_phone(old_p, new_p)
        self.autosave()
        self.view.show_message("Phone changed.")
    @input_error
    def handle_remove_phone(self, args: List[str]):
        name, p, *_ = args
        rec = self.book.find(name)
        rec.remove_phone(p)
        self.autosave()
        self.view.show_message("Phone removed.")
    @input_error
    def handle_delete(self, args: List[str]):
        name, *_ = args
        self.book.delete(name)
        self.autosave()
        self.view.show_message("Contact deleted.")
    @input_error
    def handle_phone(self, args: List[str]):
        name, *_ = args
        rec = self.book.find(name)
        self.view.show_contact(rec)
    def handle_all(self, *_):
        self.view.show_contacts(self.book.values())
    @input_error
    def handle_add_birthday(self, args: List[str]):
        name, d, *_ = args
        rec = self.book.find(name)
        rec.add_birthday(d)
        self.autosave()
        self.view.show_message("Birthday added.")
    @input_error
    def handle_show_birthday(self, args: List[str]):
        name, *_ = args
        rec = self.book.find(name)
        if rec.birthday:
            self.view.show_message(rec.birthday.value)
        else:
            self.view.show_message("Для цього контакту не задано дня народження.")
    def handle_birthdays(self, *_):
        self.view.show_birthdays(self.book.get_upcoming_birthdays(7))
    def handle_help(self, *_):
        self.view.show_help(self.commands_help)
    def run(self):
        self.view.show_welcome()
        print(f"Дані завантажено з {DEFAULT_DB}")
        try:
            while True:
                line = input("Enter a command: ")
                cmd, args = self.parse_input(line)
                if not cmd:
                    continue
                if cmd in ("exit", "close"):
                    self.view.show_goodbye()
                    break
                if cmd == "hello":
                    self.view.show_message("How can I help you?")
                elif cmd == "help":
                    self.handle_help()
                elif cmd == "add":
                    self.handle_add(args)
                elif cmd == "change":
                    self.handle_change(args)
                elif cmd == "remove-phone":
                    self.handle_remove_phone(args)
                elif cmd == "delete":
                    self.handle_delete(args)
                elif cmd == "phone":
                    self.handle_phone(args)
                elif cmd == "all":
                    self.handle_all()
                elif cmd == "add-birthday":
                    self.handle_add_birthday(args)
                elif cmd == "show-birthday":
                    self.handle_show_birthday(args)
                elif cmd == "birthdays":
                    self.handle_birthdays()
                else:
                    self.view.show_message("Invalid command. Введіть 'help' для довідки.")
        finally:
            save_data(self.book, DEFAULT_DB)
            print(f"Дані збережено у {DEFAULT_DB}")

def main():
    book = load_data(DEFAULT_DB)
    view = ConsoleView()
    app = App(book, view)
    app.run()

if __name__ == "__main__":
    main()
