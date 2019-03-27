# coding: utf-8
from ctypes import *
import os
import supervisely_lib as sly

FLOAT = c_float
PFLOAT = POINTER(c_float)

lib = CDLL("/workdir/src/darknet/libdarknet.so", RTLD_GLOBAL)

train_yolo = lib.train_supervisely
lib.train_supervisely.argtypes = [
    c_char_p, c_char_p,
    POINTER(c_char_p), POINTER(c_int), POINTER(POINTER(c_float)), c_int,
    POINTER(c_char_p), POINTER(c_int), POINTER(POINTER(c_float)), c_int,
    POINTER(c_int), c_int,
    c_int, c_int,
    c_int, c_int, c_int, c_int, c_float
]
# void train_supervisely(char *cfgfile, char *weightfile, char **img_pathes, int *num_gt_boxes, float **boxes,
#     int *gpus, int ngpus, int num_threads, int epochs, int train_steps, int layer_cutoff, int use_augm,  int print_every,
#     float bn_momentum);


def c_get_directory_size(checkpoint_file_path):
    checkpoint_path = os.path.dirname(str(checkpoint_file_path.decode('utf-8')))
    return sly.fs.get_directory_size(checkpoint_path)


_get_directory_size_type = CFUNCTYPE(c_ulonglong, c_char_p)
_get_directory_size_callback = _get_directory_size_type(c_get_directory_size)
lib.SetDirSizeCallback(_get_directory_size_callback)


def string_list_pp_char(str_list):
    arr = (c_char_p * len(str_list))()
    arr[:] = str_list
    return arr


def int1D_to_p_int(int_list):
    int_obj = c_int * len(int_list)
    return int_obj(*int_list)


def float2D_to_pp_float(float_list):
    # print(float_list[0][1])
    res = (PFLOAT * len(float_list))()
    for i, row in enumerate(float_list):
        res[i] = (FLOAT * len(row))()
        for j, val in enumerate(row):
            res[i][j] = val
    return res

