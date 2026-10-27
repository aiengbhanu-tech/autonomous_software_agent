def capped_fee(amount, rate, cap):
    return min(amount * rate, cap)
