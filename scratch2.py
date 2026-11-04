def mySqrt(x: int) -> int:
        res = 0
        d = float(x)
        while d >= 1:
            d /= 2.0
            res += 1
        return res
    

print(mySqrt(39))
print(39 / 2 / 2 / 2 / 2 / 2 / 2)