def printTable(data: list[list[str]]) -> None:
    colWidths = [0] * len(data)
    for i, j in enumerate(data):
        maxLen = len(max(j, key=len))
        colWidths[i] = maxLen

    for i in zip(*data):
        for j, k in enumerate(i):
            print(k.rjust(colWidths[j]), end=" ")
        print()


if __name__ == "__main__":
    tableData = [
        ["apples", "oranges", "cherries", "bananas"],
        ["Alice", "Bob", "Carol", "David"],
        ["dogs", "cats", "moose", "goose"],
    ]

    printTable(tableData)
