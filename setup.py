# Setup
import os
import yaml


class ServiceSetup():        
    
    def __init__(self, config_fp):
        self.config_fp = config_fp
        self.root_dir = None
        self.secret = None
        self.graphs_config = None
        self.current_graph = None
        self.ffmpeg = None
        self.whisper_cpp_dir = None

        self.load()

    @property
    def whisper_main(self):
        return os.path.join(self.whisper_cpp_dir, 'main')
    
    def whisper_model_fp(self, name):
        return os.path.join(self.whisper_cpp_dir, "models", "ggml-{}.bin".format(name))

    @property
    def audio_dir(self):
        return os.path.join(self.root_dir, "tmp", "audio")

    @property
    def stamp_dir(self):
        return os.path.join(self.root_dir, "tmp", "stamp")

    @property
    def openai_key(self):
        return self.secret.get('OPENAI_KEY')
    
    @property
    def yt_developer_key(self):
        return self.secret.get('DEVELOPER_KEY')

    @property
    def gc_project_id(self):
        return self.secret.get('PROJECT_ID')

    @property
    def gc_server_location(self):
        return self.secret.get('SERVER_LOCATION')

    @property
    def anthropic_key(self):
        return self.secret.get('ANTHROPIC_KEY')

    @property
    def graph_dir(self):
        return self.current_graph.get('path')
    
    def transcript_fp(self, fn):
        return os.path.join(self.graph_dir, 'transcriptions', fn)
    
    def change_to_graph(self, graph_name):
        self.current_graph = next( graph for graph in self.graphs_config if graph.get('name') == graph_name )

    def get_dir_for_whisper_model(self, name):
        return os.path.join(self.whisper_models_dir, name)

    def load(self):
        if not self.config_fp:
            self.config_fp = './resources/config.yml'
        if not os.path.exists(self.config_fp):
            print("Config not exists: " + self.config_fp)
            return

        with open(self.config_fp, 'r') as f:
            self.config = yaml.load(f, Loader=yaml.BaseLoader)

        with open(self.config.get('secret'), 'r') as f:
            self.secret = yaml.load(f, Loader=yaml.BaseLoader)

        self.root_dir = self.config.get("root_dir")
        self.ffmpeg = self.config.get("ffmpeg")
        self.whisper_cpp_dir = self.config.get("whisper_cpp_dir")
        self.whisper_models_dir = self.config.get("whisper_models_dir")
        self.graphs_config = self.config.get('graphs')
        self.current_graph = self.graphs_config[0]

        self.make_sure_dir_exists([
            self.audio_dir,
            self.stamp_dir,
        ])
    
    def make_sure_dir_exists(self, dirs):
        for dir in dirs:
            if not os.path.exists(dir):
                print("Dir not exists: " + dir)
                os.makedirs(dir)
    
    def get_monitor_list(self):
        return self.current_graph.get('monitor_list', [])
    
    def get_record_for(self, main_id):
        return os.path.join(self.stamp_dir, main_id)