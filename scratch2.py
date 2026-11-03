
def maxSubArray(nums: list[int]) -> tuple[int, int, int]:
    cur = best = nums[0]
    start = end = 0
    temp_start = 0
    
    for i in range(1, len(nums)):
        if cur < 0:
            cur = nums[i]
            temp_start = i
        else:
            cur += nums[i]
        if cur > best:
            best = cur
            start, end = temp_start, i

    return best, start, end


print(maxSubArray([-2,1,-3,4,-1,2,1,-5,4]))