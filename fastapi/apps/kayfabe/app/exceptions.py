class PleAuthRequiredError(Exception):
    """PLE 승부 예측에 로그인 회원 id가 필요할 때."""


class ShopItemNotFoundError(Exception):
    """상품 코드에 해당하는 상품이 없을 때."""


class ShopItemUnavailableError(Exception):
    """판매가 중단된(`is_active=False`) 상품을 사려 할 때."""


class AlreadyOwnedError(Exception):
    """이미 보유한 아이템을 같은 대상으로 다시 사려 할 때."""


class InsufficientPointsError(Exception):
    """잔액이 상품 가격보다 적을 때."""

    def __init__(self, *, price: int, balance: int) -> None:
        super().__init__(f"포인트가 부족합니다. 필요 {price}, 보유 {balance}")
        self.price = price
        self.balance = balance
