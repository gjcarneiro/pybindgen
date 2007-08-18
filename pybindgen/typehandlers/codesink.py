"""
Objects that receive generated C/C++ code lines, reindents them, and
writes them to a file, memory, or another code sink object.
"""

class CodeSink(object):
    """Abstract base class for code sinks"""
    def __init__(self):
        r'''Constructor

        >>> sink = MemoryCodeSink()
        >>> sink.writeln("foo();")
        >>> sink.writeln("if (true) {")
        >>> sink.indent()
        >>> sink.writeln("bar();")
        >>> sink.unindent()
        >>> sink.writeln("zbr();")
        >>> print sink.flush().rstrip()
        foo();
        if (true) {
            bar();
        zbr();
        
        >>> sink = MemoryCodeSink()
        >>> sink.writeln("foo();")
        >>> sink.writeln()
        >>> sink.writeln("bar();")
        >>> print len(sink.flush().split("\n"))
        4
        '''
        self.indent_level = 0 # current indent level
        self.indent_stack = [] # previous indent levels

    def _format_code(self, code):
        """Utility method for subclasses to use for formatting code
        (splits lines and indents them)"""
        assert isinstance(code, str)
        l = []
        for line in code.split('\n'):
            l.append(' '*self.indent_level + line)
        return l

    def writeln(self, line=''):
        """Write one or more lines of code"""
        raise NotImplementedError

    def indent(self, level=4):
        '''Add a certain ammount of indentation to all lines written
        from now on and until unindent() is called'''
        self.indent_stack.append(self.indent_level)
        self.indent_level += level

    def unindent(self):
        '''Revert indentation level to the value before last indent() call'''
        self.indent_level = self.indent_stack.pop()


class FileCodeSink(CodeSink):
    """A code sink that writes to a file-like object"""
    def __init__(self, file_):
        """
        Keyword Arguments:
        file_ -- a file like object
        """
        CodeSink.__init__(self)
        self.file = file_

    def writeln(self, line=''):
        """Write one or more lines of code"""
        self.file.write('\n'.join(self._format_code(line)))
        self.file.write('\n')

class MemoryCodeSink(CodeSink):
    """A code sink that keeps the code in memory,
    and can later flush the code to another code sink"""
    def __init__(self):
        "Constructor"
        CodeSink.__init__(self)
        self.lines = []

    def writeln(self, line=''):
        """Write one or more lines of code"""
        self.lines.extend(self._format_code(line))

    def flush_to(self, sink):
        """Flushes code to another code sink
        sink -- another CodeSink instance
        """
        assert isinstance(sink, CodeSink)
        for line in self.lines:
            sink.writeln(line.rstrip())
        self.lines = []

    def flush(self):
        "Flushes the code and returns the formatted output as a return value string"
        l = []
        for line in self.lines:
            l.extend(self._format_code(line))
        self.lines = []
        return "\n".join(l) + '\n'

