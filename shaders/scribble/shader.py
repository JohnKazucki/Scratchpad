
class GLSLSource:
    name: str
    code: str

    """Starting line number in the original file"""
    lineno: int

class Technique:
    """
    Attributes:
        name (str): 
        passes (Pass[]): List of pass metadata
    """
    name: str
    passes: list
    
class Pass:
    """
    Attributes:
        name (str):
        stages (Stage[]): List of GL stages used by this pass
        program (int): Compiled GL program to execute in this pass
    """
    name: str
    stages: list
    program: int
    
class Stage:
    name: str
    source_names: list # str[] of GLSLSource.name
    
class PropertyList:
    items: list

class Property:
    uniform: str
    ui_name: str
    ui_type: str
    # default: any

    @property
    def glsl_type(self) -> str:
        if self.ui_type == 'color':
            return 'vec4'
        elif self.ui_type == 'texture2D':
            return 'sampler2D' # TODO: Correct?

        # Everything else is defined exact
        return self.ui_type

class ScribbleShader:
    properties: list # Property[]
    sources: dict # Map<string, GLSLSource>
    techniques: dict # Map<string, Technique>

    GLSL_VERSION = '330 core'
    COMPUTE_VERSION = '440'

    def __init__(self, blocks):
        self.properties = []
        self.sources = {}
        self.techniques = {}
        
        for block in blocks:
            if isinstance(block, PropertyList):
                self.properties = block.items
            elif isinstance(block, GLSLSource):
                self.sources[block.name] = block
            elif isinstance(block, Technique):
                self.techniques[block.name] = block
        # if technique is unnamed, set to Main.
        # if Main exists, throw? 
        # if there's no Main technique, throw. 
        
    def generate_uniforms(self) -> str:
        builtin = '''
            // Autogenerated builtins
            uniform mat4 ModelViewProjectionMatrix;
            uniform mat4 ModelMatrix;
            uniform int _Time;
            uniform vec4 _MainLightColor;
            uniform vec4 _MainLightDirection;
            uniform vec4 _AmbientColor;
        '''

        # Generate a uniform per property 
        properties = '\n// Autogenerated properties\n'
        for prop in self.properties:
            properties += 'uniform {} {};\n'.format(
                prop.glsl_type,
                prop.uniform
            )

        return builtin + properties

    def generate_inputs(self) -> str:
        # TODO: These can come from VAO enums
        return '''
            // Autogenerated attributes            
            layout(location = 0) in vec3 Position;
            layout(location = 1) in vec3 Normal;
            layout(location = 2) in vec3 Texcoord0;
            layout(location = 3) in vec3 Texcoord1;
            layout(location = 4) in vec3 Texcoord2;
        '''

    def generate_outputs(self) -> str:
        return 'out vec4 FragColor;\n'
    
    def compile_program(self, sources) -> int:
        print('-----  COMPILE -----')
        for name in sources:
            print('---- {} ----'.format(name))
            print(sources[name])

        return 0

    def combine_sources(self, names: list) -> str:
        """Combine GLSLSource code into a single string"""
        glsl = ''
        for name in names:
            src = self.sources[name]
            # Inject a #line directive to point to the originating source
            # TODO: ID reference as well to help point to the block? 
            # I'd like to differentiate errors between user code + internal codegen
            glsl += '\n#line {}\n'.format(src.lineno - 1)
            glsl += src.code

        return glsl

    def compile(self):
        """Compile GL programs for all passes in all techniques"""
        # Generate attributes/uniforms/etc shared across all programs
        version = '#version {}\n\n'.format(self.GLSL_VERSION)
        inputs = self.generate_inputs()
        outputs = self.generate_outputs()
        uniforms = self.generate_uniforms()

        for t in self.techniques.values():
            for p in t.passes:
                sources = {}
                for stage in p.stages:
                    # TODO: Handling precompute stages

                    # Add common attributes and uniforms
                    glsl = version
                    if stage.name == 'Vertex':
                        glsl += inputs
                    elif stage.name == 'Fragment':
                        glsl += outputs

                    glsl += uniforms + '\n'
                    glsl += self.combine_sources(stage.source_names)
                    sources[stage.name] = glsl

                p.program = self.compile_program(sources)

    def draw(self, technique: str):
        """Theory:

        for each technique
            get the one matching the name, or 
            the default technique if not found

            for each program (passes):
                bind the program
                set the uniforms from properties
                draw the list of meshes
                unbind the program
        """
        pass