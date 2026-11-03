
def maxSubArray(nums: list[int]) -> tuple[int, int, int]:
    cur = best = nums[0]
    start = end = 0        # indices of the best subarray so far
    temp_start = 0         # where the current run began

    for i in range(1, len(nums)):
        if cur < 0:                # the old run only hurts, start fresh here
            cur = nums[i]
            temp_start = i
        else:
            cur += nums[i]

        if cur > best:
            best = cur
            start, end = temp_start, i

    return best, start, end


print(maxSubArray([-2,1,-3,4,-1,2,1,-5,4,-6,11]))