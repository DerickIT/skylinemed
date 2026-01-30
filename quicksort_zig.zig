const std = @import("std");

fn quicksort(comptime T: type, arr: []T) void {
    if (arr.len <= 1) return;

    const pivot_index = partition(T, arr);

    const left = arr[0..pivot_index];
    const right = arr[pivot_index + 1 ..];

    quicksort(T, left);
    quicksort(T, right);
}

fn partition(comptime T: type, arr: []T) usize {
    const pivot_index = arr.len - 1;
    var i: usize = 0;

    for (arr[0..pivot_index], 0..) |*item, j| {
        if (item.* <= arr[pivot_index]) {
            const temp = arr[i];
            arr[i] = arr[j];
            arr[j] = temp;
            i += 1;
        }
    }

    const temp = arr[i];
    arr[i] = arr[pivot_index];
    arr[pivot_index] = temp;

    return i;
}

pub fn main() !void {
    const stdout = std.io.getStdOut().writer();

    var numbers = [_]i32{ 64, 34, 25, 12, 22, 11, 90, 5, 88, 42 };

    try stdout.print("Before sort: {any}\n", .{numbers});

    quicksort(i32, &numbers);

    try stdout.print("After sort: {any}\n", .{numbers});
}