import enum


class OperationType(str, enum.Enum):
    income = "income"      # доход
    expense = "expense"    # расход


class DebtDirection(str, enum.Enum):
    i_owe = "i_owe"            # я должен
    owed_to_me = "owed_to_me"  # мне должны
