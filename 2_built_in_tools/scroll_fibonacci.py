# Scroll of Fibonacci Conjuration
# When invoked, this spell summons the first 10 Fibonacci numbers.

def cast_fibonacci_spell():
    fib = [0, 1]
    for _ in range(8):
        fib.append(fib[-1] + fib[-2])
    return fib

if __name__ == "__main__":
    conjured = cast_fibonacci_spell()
    print("Behold the summoned Fibonacci sequence:")
    print(conjured)