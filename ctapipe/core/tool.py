from traitlets.config import Application, boolean_flag
from traitlets import Unicode


class Tool(Application):
    """A base class for all executable tools (applications) that handles
    configuration loading/saving, logging, command-line processing,
    and provenance meta-data handling. It is based on
    `traitlets.config.Application`. Tools may contain configurable
    `ctapipe.core.Component` classes that do work, and their
    configuration parameters will propegate automatically to the
    `Tool`.

    Tool developers should create sub-classes, and a name,
    description, usage examples should be added by defining the
    `name`, `description` and `examples` class attributes as
    strings. The `aliases` attribute can be set to cause a lower-level
    `Component` parameter to become a high-plevel command-line
    parameter (See example below). The `initialize()`, `start()`, and
    `finish()` methods should be defined in the sub-class.

    Additionally, any `ctapipe.core.Component` used within the `Tool`
    should have their class in a list in the `classes` attribute,
    which will automatically add their configuration parameters to the
    tool.

    Once a tool is constructed and the virtual methods defined, the
    user can call the `run()` method to initialize and start it.


    .. code:: python

        from ctapipe.core import Tool
        from traitlets import (Integer, Float, List, Dict, Unicode)

        class MyTool(Tool):
            name = "mytool"
            description = "do some things and stuff"
            aliases = Dict(dict(infile='AdvancedComponent.infile',
                                log_level='MyTool.log_level',
                                iterations='MyTool.iterations'))

            # Which classes are registered for configuration
            classes = List([MyComponent, AdvancedComponent, SecondaryMyComponent])

            # local configuration parameters
            iterations = Integer(5,help="Number of times to run", 
                                 allow_none=False).tag(config=True)

            def init_comp(self):
                self.comp = MyComponent(self, config=self.config)
                self.comp2 = SecondaryMyComponent(self, config=self.config)

            def init_advanced(self):
                self.advanced = AdvancedComponent(self, config=self.config)

            def initialize(self):
                self.init_comp()
                self.init_advanced()

            def start(self):
                self.log.info("Performing {} iterations...".format(self.iterations))
                for ii in range(self.iterations):
                    self.log.info("ITERATION {}".format(ii))
                    self.comp.do_thing()
                    self.comp2.do_thing()
                    sleep(0.5)

            def finish(self):
                self.log.warning("Shutting down.")

        def main():
            tool = MyTool()
            tool.run()

        if __name__ == "main":
           main()


    If this `main()` method is registered in `setup.py` under
    *entry_points*, it will become a command-line tool (see examples
    in the `ctapipe/tools` subdirectory).

    """

    def __init__(self, **kwargs):
        # make sure there are some default aliases in all Tools:
        if self.aliases:
            self.aliases['log_level'] = 'Application.log_level'
        super().__init__(**kwargs)

    config_file = Unicode( help="name of configuration file with parameters")\
        .tag(config=True)

    def _setup(self, argv=None):
        """ handle config and any other low-level setup """
        self.parse_command_line(argv)
        if self.config_file:
            self.load_config_file(self.config_file)
        self.initialize()

    def initialize(self):
        """set up the tool (override in subclass). Here the user should
        construct all `Components` and open files, etc."""
        super().initialize(argv=None)

    def start(self):
        """main body of tool (override in subclass). This is automatially
        called after `initialize()` when the `run()` is called.
        """
        pass

    def finish(self):
        """finish up (override in subclass). This is called automatially
        after `start()` when `run()` is called."""
        self.log.info("Goodbye")

    def run(self, argv=None):
        """Run the tool. This automatically calls `initialize()`,
        `start()` and `finish()`
        """
        try:
            self._setup(argv)
            self.log.info("Starting: {}".format(self.name))
            self.log.debug("CONFIG: {}".format(self.config))
            self.start()
            self.finish()
        except Exception as err:
            self.log.error('Caught unexpected exception: {}'.format(err))
