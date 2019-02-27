# import framework_pb2
import sys


def listOps(read_path):
    read_file = open(read_path)
    flag = False
    for line in read_file:
        arr = line.split()
        if len(arr) > 0:
            if cmp('ops', arr[0]) == 0:
                flag = True
            if cmp('vars', arr[0]) == 0 or cmp('attrs', arr[0]) == 0:
                flag = False
            if flag and cmp('type:', arr[0]) == 0:
                print(eval(arr[1]))
    read_file.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: ", sys.argv[0], "BOOK_PROGRAM_FILE_PATH")
        sys.exit(-1)

    listOps(sys.argv[1])
