class ChangeBox:
    def __init__(self):
        self.denominations = {
            10: 50,
            20: 50,
            50: 50,
            100: 50,
            200: 50
        }

    def give_change(self, amount):
        if amount % 10:
            raise RuntimeError
        while amount:
            for d in self.denominations:
                if d <= amount:
                    amount -= d
                    pin = self.denominations[d]
                    # do something with pin
                    break
        return True
