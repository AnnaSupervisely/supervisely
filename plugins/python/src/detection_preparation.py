src_project_name = 'CHANGE_TO_YOUR_INPUT_PROJECT_NAME'
dst_project_name = 'CHANGE_TO_YOUR_DESTINATION_PROJECT_NAME'

# Which fraction of images to tag as a validation set (remaining are tagged as training set).
validation_fraction = 0.1
# How many random crops per image to save.
crops_per_image = 5

min_crop_side_fraction = 0.6
max_crop_side_fraction = 0.9

train_tag_name = 'train'  # Reasonable default, change is necessary
val_tag_name = 'val'      # Reasonable default, change is necessary


import os.path
from supervisely_lib.nn import dataset as sly_dataset


# Download remote project
src_project_info = api.project.get_info_by_name(WORKSPACE_ID, src_project_name)
src_project_dir = os.path.join(sly.TaskPaths.DATA_DIR, src_project_name)

sly.logger.info('DOWNLOAD_PROJECT', extra={'title': src_project_name})
sly.download_project(api, src_project_info.id, src_project_dir, log_progress=True)
sly.logger.info('Project {!r} has been successfully downloaded. Starting to process.'.format(src_project_name))

src_project = sly.Project(directory=src_project_dir, mode=sly.OpenMode.READ)

dst_project_dir = os.path.join(RESULT_DATASETS_DIR, dst_project_name)
dst_project = sly.Project(directory=dst_project_dir, mode=sly.OpenMode.CREATE)

tag_meta_train = sly.TagMeta(train_tag_name, sly.TagValueType.NONE)
tag_meta_val = sly.TagMeta(val_tag_name, sly.TagValueType.NONE)

bbox_class_mapping = {
    obj_class.name: (
        obj_class if (obj_class.geometry_type == sly.Rectangle)
        else sly.ObjClass(obj_class.name + '_bbox', sly.Rectangle, color=obj_class.color))
    for obj_class in src_project.meta.obj_classes}

dst_meta = src_project.meta.clone(
    obj_classes=sly.ObjClassCollection(bbox_class_mapping.values()),
    tag_metas=src_project.meta.tag_metas.add_items([tag_meta_train, tag_meta_val]))
dst_project.set_meta(dst_meta)

crop_side_fraction = (min_crop_side_fraction, max_crop_side_fraction)

total_images = api.project.get_images_count(src_project_info.id)
if total_images <= 1:
    raise RuntimeError('Need at least 2 images in a project to prepare a training set (at least 1 each for training '
                       'and validation).')
is_train_image = sly_dataset.partition_train_val(total_images, validation_fraction)

# Iterate over datasets and items.
image_idx = 0
for dataset in src_project:
    sly.logger.info('Dataset processing', extra={'dataset_name': dataset.name})
    dst_dataset = dst_project.create_dataset(dataset.name)

    for item_name in dataset:
        item_paths = dataset.get_item_paths(item_name)
        img = sly.image.read(item_paths.img_path)
        ann = sly.Annotation.load_json_file(item_paths.ann_path, src_project.meta)

        # Decide whether this image and its crops should go to a train or validation fold.
        tag = sly.Tag(tag_meta_train) if is_train_image[image_idx] else sly.Tag(tag_meta_val)
        ann = ann.add_tag(tag)

        # Convert all the objects to bounding boxes for detection.
        bbox_labels = [
            label.clone(obj_class=bbox_class_mapping[label.obj_class.name], geometry=label.geometry.to_bbox())
            for label in ann.labels]
        ann = ann.clone(labels=bbox_labels)

        augmented_items = sly.aug.flip_add_random_crops(
            img, ann, crops_per_image, crop_side_fraction, crop_side_fraction)
        aug_imgs, aug_anns = zip(*augmented_items)

        names = sly.generate_names(item_name, len(augmented_items))
        for aug_name, aug_img, aug_ann in zip(names, aug_imgs, aug_anns):
            dst_dataset.add_item_np(item_name=aug_name, img=aug_img, ann=aug_ann)

        image_idx += 1

sly.logger.info('Finished: project {!r} prepared for detection.'.format(dst_project_name))
