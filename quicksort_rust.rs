fn quicksort<T: Ord>(arr: &mut [T]) {
    if arr.len() <= 1 {
        return;
    }

    let pivot_index = partition(arr);

    let (left, right) = arr.split_at_mut(pivot_index);
    quicksort(left);
    // Skip the pivot element
    if !right.is_empty() {
        quicksort(&mut right[1..]);
    }
}

fn partition<T: Ord>(arr: &mut [T]) -> usize {
    let len = arr.len();
    let pivot_index = len - 1;
    let mut i = 0;

    for j in 0..pivot_index {
        if arr[j] <= arr[pivot_index] {
            arr.swap(i, j);
            i += 1;
        }
    }

    arr.swap(i, pivot_index);
    i
}

fn main() {
    let mut numbers = vec![64, 34, 25, 12, 22, 11, 90, 5, 88, 42];
    println!("Before sort: {:?}", numbers);

    quicksort(&mut numbers);

    println!("After sort: {:?}", numbers);
}