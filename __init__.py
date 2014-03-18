'''
Created on Mar 17, 2014

@author: Patrick
'''
import bpy
import bgl
import blf
from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.geometry import intersect_line_plane


bl_info = {
    "name": "Curve Extrude",
    "author": "Patrick Moore",
    "version": (0, 0, 0),
    "blender": (2, 7, 0),
    "location": "Curve > Extrude",
    "description": "Extends curve objects with drawn strokes",
    "warning": "",
    "wiki_url": "",
    "category": "Edit Curve"}
 
def draw_callback_px(self, context):
    
    font_id = 0  # XXX, need to find out how best to get this.
 
    # draw some text
    blf.position(font_id, 15, 30, 0)
    blf.size(font_id, 20, 72)
    blf.draw(font_id, "Hello Word " + str(len(self.mouse_path)))
 
    # 50% alpha, 2 pixel width line
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 0.5)
    bgl.glLineWidth(2)
 
    bgl.glBegin(bgl.GL_LINE_STRIP)
    for x, y in self.mouse_path:
        bgl.glVertex2i(x, y)
 
    bgl.glEnd()
    
    # 50% alpha, 2 pixel width line
    
    bgl.glColor4f(0.0, 1, 0.0, 1)
    bgl.glPointSize(5)
    bgl.glBegin(bgl.GL_POINTS)
    for v in self.spline_end_dict:
        bgl.glVertex2f(v[0], v[1])
        
    bgl.glEnd()
 
    # restore opengl defaults
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
 
 
class CurveModalExtrude(bpy.types.Operator):
    """Draw a line with the mouse to extrude bezier curves"""
    bl_idname = "curve.modal_extrude"
    bl_label = "Extrude Curve"

    @classmethod
    def poll(cls, context):
        
        for ob in context.scene.objects:
            if ob.type == 'CURVE' and not ob.hide:
                return True
        
        return
    
    def update_curve_points(self,context):
        region = context.region
        rv3d = context.region_data
        
        self.spline_end_dict = {}
        
        for ob in context.scene.objects:
            if ob.type == 'CURVE' and not ob.hide:
                for spline in ob.data.splines:
                    if not spline.use_cyclic_u:
                        coord = ob.matrix_world * spline.bezier_points[-1].co
                        screen_coord = view3d_utils.location_3d_to_region_2d(region, rv3d, coord)
                        if screen_coord: #it could be off screen
                            self.spline_end_dict[tuple(screen_coord)] = spline, ob
    
    def find_active_spline(self, context, x, y):
        
        def dist(v):
            '''
            v is a tuple because Vectors aren't hashable
            '''
            return (Vector(v) - Vector((x,y))).length
        
        #thank goodness dictionaries are iterable over keys
        point  = min(self.spline_end_dict, key = dist)
        
        if dist(point) < 20:
            spline, ob = self.spline_end_dict[point]
        else:
            spline, ob = None, None
            
        return spline, ob
    
    def mousemove_drawing(self, context, event):
        screen_v = Vector((event.mouse_region_x, event.mouse_region_y))
        self.mouse_path.append((event.mouse_region_x, event.mouse_region_y))
       
        #this will just add in apoint every 10 recorded mouse positions
        #later you will want to do something smarter :-)
        if len(self.mouse_path) > self.draw_points_max or (screen_v - Vector(self.mouse_path[0])).length >= self.extrusion_radius:
            region = context.region
            rv3d = context.region_data
            #this is the view_vector @ the mous coord
            #which is not the same as the view_direction!!!
            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, self.mouse_path[-1])
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, self.mouse_path[-1])
            ray_target = ray_origin + (view_vector * 10000)
           
            #cast the ray into a plane a
            #perpendicular to the view dir, at the last bez point of the curve
            
            view_direction = rv3d.view_rotation * Vector((0,0,-1))
            plane_pt = self.curve_object.matrix_world * self.active_spline.bezier_points[-1].co
            new_coord = intersect_line_plane(ray_origin, ray_target,plane_pt, view_direction)
           
            if new_coord:
               
                self.active_spline.bezier_points.add(1)
                self.active_spline.bezier_points[-1].co = self.curve_object.matrix_world.inverted() * new_coord
                self.active_spline.bezier_points[-1].handle_right.xyz = self.active_spline.bezier_points[-1].co
                self.active_spline.bezier_points[-1].handle_left.xyz = self.active_spline.bezier_points[-1].co
                self.active_spline.bezier_points[-1].handle_left_type = 'AUTO'
                self.active_spline.bezier_points[-1].handle_right_type = 'AUTO'
               
                #udpate everything
                #udpate modifiers and objects etc.
                self.curve_object.update_tag()
                context.scene.update()
               
            self.mouse_path = []
        
    def modal(self, context, event):
        context.area.tag_redraw()
 
        if event.type == 'MOUSEMOVE' and self.draw:
            self.mousemove_drawing(context, event)
            
        elif event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.active_spline, self.curve_object = self.find_active_spline(context, event.mouse_region_x, event.mouse_region_y)
                if self.active_spline:
                    self.draw = True
                else:
                    self.draw = False
            else:
                self.draw = False
                self.mouse_path = []
                self.update_curve_points(context)
                
               
 
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}
           
           
        return {'RUNNING_MODAL'}
 
    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            # the arguments we pass the the callback
            args = (self, context)
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
 
            #keep some mouse points
            self.mouse_path = []
            self.draw = False
            self.draw_points_max = 15   #points in the draw cache
            self.extrusion_radius = 75  #pixels
            
            #hang on to a mapping of splines and objects by their endpoint
            self.spline_end_dict = {}
            self.active_spline = None
            self.curve_object = None
            
            self.update_curve_points(context)
            
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}
 
 
def register():
    bpy.utils.register_class(CurveModalExtrude)
 
 
def unregister():
    bpy.utils.unregister_class(CurveModalExtrude)
