# coding: utf-8

import os
from os.path import join

import cv2
import numpy as np
from PIL import Image
import supervisely_lib as sly
from supervisely_lib.dtl_utils import dtl_paths
from supervisely_lib.imaging import color as color_utils
from supervisely_lib.figure.figure_bitmap import FigureBitmap
from supervisely_lib.io.json import dump_json_file, load_json_file
from supervisely_lib.project.annotation import Annotation
from supervisely_lib.project.project_structure import ProjectStructure, ProjectFS
from supervisely_lib.project.project_meta import ProjectMeta
from supervisely_lib.tasks import progress_counter


class ImporterAberystwyth:
    true_subdirs = ['PSI_Tray031', 'PSI_Tray032']

    def __init__(self):
        task_paths = dtl_paths.DtlPaths()
        self.in_dir = task_paths.data_dir
        self.out_dir = task_paths.results_dir
        self.settings = load_json_file(task_paths.settings_path)

        if len(task_paths.project_dirs) != 1:
            raise RuntimeError('Invalid data format. Input folder should contain only "images_and_annotations" dir')
        self.data_dir = join(self.in_dir, 'images_and_annotations')

    def _get_ann(self, image_id, masks_map, image_size, project_meta: ProjectMeta):
        figures = []

        mask = cv2.imread(masks_map[os.path.basename(image_id)])[:, :, ::-1]
        colors = np.unique(mask.reshape(-1, mask.shape[2]), axis=0)
        for color in colors:
            if not np.all(color == 0):
                bool_mask = np.all(mask == color, axis=2)
                figures.extend(FigureBitmap.from_mask('leaf', (0, 0), bool_mask))

        ann = Annotation.new_with_objects(image_size, figures, project_meta)
        return ann

    def _convert_sample(self, sample_info, masks_map, project_meta: ProjectMeta):
        image_name = sample_info.image_name
        src_image_path = sample_info.ia_data['image_orig_path']

        src_image = np.array(Image.open(src_image_path))

        cv2.imwrite(sample_info.img_path, src_image[:, :, ::-1])
        ann = self._get_ann(image_name, masks_map, src_image.shape[:2], project_meta)
        packed_ann = ann.pack()
        dump_json_file(packed_ann, sample_info.ann_path)

    @staticmethod
    def _get_files_list(dir_path):
        files_list = [file for file in os.listdir(dir_path) if os.path.isfile(join(dir_path, file))]
        return files_list

    def _get_images_pathes(self):
        images_list = []
        for subdir in self.true_subdirs:
            images_list.extend([join(self.data_dir, subdir, 'tv', fp)
                                for fp in self._get_files_list(join(self.data_dir, subdir, 'tv'))])
        return images_list

    def _get_masks_mapping(self):
        masks_map = {}
        for subdir in self.true_subdirs:
            masks_map.update({os.path.splitext(mask_p)[0].replace('_gt', ''): join(self.data_dir, subdir, 'tv', 'gt', mask_p)
                              for mask_p in self._get_files_list(join(self.data_dir, subdir, 'tv', 'gt'))})
        return masks_map

    def convert(self):
        images_pathes = self._get_images_pathes()
        masks_map = self._get_masks_mapping()
        dataset_name = 'ds'
        out_pr = ProjectStructure(self.settings['res_names']['project'])

        for image_fp in images_pathes:
            base_name = os.path.basename(image_fp)
            image_ext = os.path.splitext(image_fp)[1]
            image_id = os.path.splitext(base_name)[0]
            if base_name.replace(image_ext, '') in masks_map:
                dt = {
                    "image_ext": ".png",
                    "image_orig_path": image_fp
                }
                out_pr.add_item(dataset_name, image_id, dt)

        out_pr_fs = ProjectFS(self.out_dir, out_pr)
        out_pr_fs.make_dirs()

        res_meta = ProjectMeta()
        # TODO: Fix it line by new meta and object classes
        res_meta.classes.add(
            {'title': 'leaf', 'shape': 'bitmap', 'color': color_utils.rgb2hex(color_utils.random_rgb())})
        res_meta.to_dir(out_pr_fs.project_path)

        progress = progress_counter.progress_counter_import(out_pr.name, out_pr.image_cnt)
        for sample_info in out_pr_fs:
            self._convert_sample(sample_info, masks_map, res_meta)
            progress.iter_done_report()


def main():
    importer = ImporterAberystwyth()
    importer.convert()
    sly.report_import_finished()


if __name__ == '__main__':
    sly.main_wrapper('ABERYSTWYTH_IMPORT', main)
