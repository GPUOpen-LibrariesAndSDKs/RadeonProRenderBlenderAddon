import inspect
import weakref

import bpy
import numpy as np

from rprblender import logging, rpraddon
from rprblender.helpers import CallLogger


@rpraddon.register_class
class RPRRefreshImageOperator(bpy.types.Operator):
    bl_idname = "rpr.refresh_image"
    bl_label = "Refresh Image"

    @classmethod
    def poll(cls, context):
        return context.space_data and 'IMAGE_EDITOR' == context.space_data.type and context.space_data.image

    def execute(self, context):
        logging.debug("cleaning:", context.space_data.image)
        image_cache.delete_image_pixels(context.space_data.image)
        return {'FINISHED'}


@rpraddon.register_class
class RPRImageCachePurgeOperator(bpy.types.Operator):
    bl_idname = "rpr.image_cache_purge"
    bl_label = "Purge Image Cache"

    @classmethod
    def poll(cls, context):
        return context.space_data and 'IMAGE_EDITOR' == context.space_data.type

    def execute(self, context):
        logging.debug("cleaning:", context.space_data.image)
        image_cache.purge()
        downscaled_image_cache.purge()
        core_image_cache.purge()
        core_downscaled_image_cache.purge()
        return {'FINISHED'}


use_downscaled_images = {}

class ImageCacheStats:
    def __init__(self):
        self.stats4image = {}

    def loaded(self, image, pixels):
        self.stats4image[image][1] += pixels.shape[0] * pixels.shape[1]

    def requested(self, image):
        if image not in self.stats4image:
            self.stats4image[image] = [0, 0]
        self.stats4image[image][0] += 1

    def deleted(self, image):
        del self.stats4image[image]

    def format_current(self):
        requests = sum(s[0] for s in self.stats4image.values())
        image_count = len(self.stats4image)
        return "images: {images}, total size: {total_size}Mb, requests:{requests}, request per image: {request_per_image}, virtual size requested: {virtual_size} Mb".format(
            images=image_count,
            total_size=sum(s[1] for s in self.stats4image.values()) / (1024 * 1024) * 16,
            requests=requests,
            request_per_image=requests / image_count if image_count else '-',
            virtual_size=sum(s[0] * s[1] for s in self.stats4image.values()) / (1024 * 1024) * 16,
        )


class ImageCache:
    def __init__(self, name):
        self.image2pixels = {}
        self.stats = ImageCacheStats()
        self.name = name

    def get_image_pixels(self, image, load_pixels_from_blender_image):
        self.stats.requested(image)

        if image in self.image2pixels:
            pixels = self.image2pixels[image]
        else:
            pixels = load_pixels_from_blender_image(image)
            self.image2pixels[image] = pixels
            self.stats.loaded(image, pixels)

        logging.debug("ImageCache(%s).get_image_pixels, images=%d, loading image: %s" % 
                      (self.name, len(self.image2pixels), image.name))

        return pixels

    def delete_image_pixels(self, image):
        if image in self.image2pixels:
            del self.image2pixels[image]
            self.stats.deleted(image)

    def purge(self):
        self.image2pixels.clear()
        self.stats = ImageCacheStats()


image_cache = ImageCache("original")
downscaled_image_cache = ImageCache("downscaled")


class CoreImageCache:
    def __init__(self, name):
        self.images4context = weakref.WeakKeyDictionary()
        self.name = name

    def get_core_image(self, context, image, load_image):
        images = self.images4context.setdefault(context, {})
        if image in images:
            ret = images[image]
        else:
            ret = images.setdefault(image, load_image(context, image))

        logging.debug("CoreImageCache(%s).get_core_image, context_id=%d, images=%d, loading image: %s" % 
                      (self.name, id(context), len(images), image.name))
        return ret

    def purge(self):
        self.images4context.clear()

    def purge_for_context(self, core_context):
        self.images4context.get(core_context, {}).clear()

    def get_info(self):
        str = "CoreImageCache(%s): contexts number=%d" % (self.name, len(self.images4context))
        str_list = []
        for context, images in self.images4context.items():
            str_list.append("\n    context_id=%d, images=%d" % (id(context), len(images)))
        return str + "".join(str_list)


core_image_cache = CoreImageCache("original")
core_downscaled_image_cache = CoreImageCache("downscaled")


@bpy.app.handlers.persistent
def update_post(scene):
    if bpy.data.images.is_updated:
        logging.info(inspect.currentframe().f_code.co_name, "bpy.data.images.is_updated")
    for image in bpy.data.images:
        if image.is_updated or image.is_updated_data:
            logging.info(inspect.currentframe().f_code.co_name, "image updated", image, image.as_pointer())

            # for material in bpy.data.materials:
            #     if material.is_updated or material.is_updated_data:
            #         logging.info(inspect.currentframe().f_code.co_name, "material updated", material)
            #
            # for texture in bpy.data.textures:
            #     if texture.is_updated or texture.is_updated_data:
            #         logging.info(inspect.currentframe().f_code.co_name, "texture updated", texture)
            #
            # for node_group in bpy.data.node_groups:
            #     if node_group.is_updated or node_group.is_updated_data:
            #         logging.info(inspect.currentframe().f_code.co_name, "node_group updated", node_group)


update_pre = update_post


@bpy.app.handlers.persistent
def load_post(context):
    logging.info(__file__, inspect.currentframe().f_code.co_name)
    image_cache.purge()
    core_image_cache.purge()


def register():
    bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.scene_update_pre.append(update_pre)
    bpy.app.handlers.scene_update_post.append(update_post)


def unregister():
    bpy.app.handlers.load_post.remove(load_post)
    bpy.app.handlers.scene_update_pre.remove(update_pre)
    bpy.app.handlers.scene_update_post.remove(update_post)
