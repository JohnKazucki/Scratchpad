
import os
from time import time

from .base import (
    BaseShader, 
    ShaderProperties,
)

from ..parsers.glsl.preprocessor import GLSLPreprocessor

class GLSLShader(BaseShader):
    """Direct GLSL shader from GLSL source files"""

    # Version directive to automatically add to source files
    COMPAT_VERSION = '330 core'

    # Maximum lights to send to shaders as _AdditionalLights* uniforms
    MAX_ADDITIONAL_LIGHTS = 16

    def __init__(self):
        super(GLSLShader, self).__init__()

        self.properties = ShaderProperties()
        # self.properties.add('boolean', 'use_composite_file', 'Use Separate Stage Sources', '')
        # self.properties.add('source_file', 'composite_file', 'Source File', 'GLSL Source file containing all stages')

        self.properties.add('source_file', 'vert_filename', 'Vertex', 'GLSL Vertex shader source file')
        self.properties.add('source_file', 'tesc_filename', 'Tessellation Control', 'GLSL Tessellation Control shader source file')
        self.properties.add('source_file', 'tese_filename', 'Tessellation Evaluation', 'GLSL Tessellation Evaluation shader source file')
        self.properties.add('source_file', 'geom_filename', 'Geometry', 'GLSL Geometry shader source file')
        self.properties.add('source_file', 'frag_filename', 'Fragment', 'GLSL Fragment shader source file')

        self.properties.add('image', 'diffuse', 'Diffuse', 'Diffuse color channel image')
        self.material_properties = ShaderProperties()

    def get_renderer_properties(self):
        return self.properties

    def update_renderer_properties(self, settings):
        self.properties.from_property_group(settings)
        
        if not os.path.isfile(settings.vert_filename):
            raise FileNotFoundError('Missing required vertex shader')
            
        if not os.path.isfile(settings.frag_filename):
            raise FileNotFoundError('Missing required fragment shader')
        
        self.stages = { 
            'vs': settings.vert_filename,
            'tcs': settings.tesc_filename, 
            'tes': settings.tese_filename,
            'gs': settings.geom_filename,
            'fs': settings.frag_filename
        }
        
        self.monitored_files = [f for f in self.stages.values() if f]

        # TODO: More dynamic (iterate properties, track each one that's an image)
        self.diffuse = settings.diffuse

    def get_material_properties(self):
        return self.material_properties

    def update_material_properties(self, settings):
        self.material_properties.from_property_group(settings)
        
    def recompile(self):
        sources = {}

        # Mapping between a shader stage and array of include files.
        # Used for resolving the source of compilation errors
        # TODO: Implement as part of the compilation process - somehow.
        # (Probably as a feature of base shader - since everything can do this)
        self.includes = {}
        
        preprocessor = GLSLPreprocessor()

        for stage, filename in self.stages.items():
            source = None
            if filename:
                # TODO: Stage defines (e.g. #define VERTEX - useful?)
                # Would be more useful if there was a single input field
                source = '#version {}\n{}'.format(
                    self.COMPAT_VERSION, 
                    preprocessor.parse_file(filename)
                )
                self.includes[stage] = preprocessor.includes

            sources[stage] = source

        self.compile_from_strings(
            sources['vs'], 
            sources['fs'], 
            sources['tcs'], 
            sources['tes'], 
            sources['gs']
        )

        self.update_mtimes()

    def bind_textures(self):
        # TODO: WIP
        if self.diffuse:
            print('binding diffuse', self.diffuse.bindcode)
            self.bind_texture(0, 'diffuse', self.diffuse)
        else:
            print('no diffuse')

    def bind(self):
        super(GLSLShader, self).bind()

        # TODO: Doesn't work, number too big. Change this up
        # self.set_float("_Time", time())
        self.bind_textures()

    def set_camera_matrices(self, view_matrix, projection_matrix):
        self.view_matrix = view_matrix
        self.projection_matrix = projection_matrix

        self.set_mat4("ViewMatrix", view_matrix.transposed())
        self.set_mat4("ProjectionMatrix", projection_matrix.transposed())
        self.set_mat4("CameraMatrix", view_matrix.inverted().transposed())

    def set_object_matrices(self, model_matrix):
        mv = self.view_matrix @ model_matrix
        mvp = self.projection_matrix @ mv

        self.set_mat4("ModelMatrix", model_matrix.transposed())
        self.set_mat4("ModelViewMatrix", mv.transposed())
        self.set_mat4("ModelViewProjectionMatrix", mvp.transposed())
        
    def set_lighting(self, lighting):
        """Copy lighting information into shader uniforms
        
        This is inspired by Unity's URP where there is a main directional light
        and a number of secondary lights packed into an array buffer. 

        This particular implementation doesn't account for anything advanced
        like shadows, light cookies, etc. Nor does it try to calculate per-object
        light arrays to support a ridiculous number of lights. 

        Parameters:
            lighting (SceneLighting): Current scene lighting information
        """
        limit = self.MAX_ADDITIONAL_LIGHTS

        positions = [0] * (limit * 4)
        directions = [0] * (limit * 4)
        colors = [0] * (limit * 4)
        attenuations = [0] * (limit * 4)

        # Feed lights into buffers
        i = 0
        for light in lighting.additional_lights.values():
            # print('Light', i)
            v = light.position
            # print('    Position', v)
            positions[i * 4] = v[0]
            positions[i * 4 + 1] = v[1]
            positions[i * 4 + 2] = v[2]
            positions[i * 4 + 3] = v[3]
            
            v = light.direction
            # print('    Direction', v)
            directions[i * 4] = v[0]
            directions[i * 4 + 1] = v[1]
            directions[i * 4 + 2] = v[2]
            directions[i * 4 + 3] = v[3]

            v = light.color
            # print('    Color', v)
            colors[i * 4] = v[0]
            colors[i * 4 + 1] = v[1]
            colors[i * 4 + 2] = v[2]
            colors[i * 4 + 3] = v[3]

            v = light.attenuation
            # print('    Attenuation', v)
            attenuations[i * 4] = v[0]
            attenuations[i * 4 + 1] = v[1]
            attenuations[i * 4 + 2] = v[2]
            attenuations[i * 4 + 3] = v[3]

            i += 1
        
        if lighting.main_light:
            self.set_vec4("_MainLightDirection", lighting.main_light.direction)
            self.set_vec4("_MainLightColor", lighting.main_light.color)

        self.set_int("_AdditionalLightsCount", i)
        self.set_vec4_array("_AdditionalLightsPosition", positions)
        self.set_vec4_array("_AdditionalLightsColor", colors)
        self.set_vec4_array("_AdditionalLightsSpotDir", directions)
        self.set_vec4_array("_AdditionalLightsAttenuation", attenuations)
        
        self.set_vec3("_AmbientColor", lighting.ambient_color)
