class CommandBlock:
    def __init__(self, command, conditional=True, mode='CHAIN', auto=True):
        self.command = command
        self.cond = conditional
        self.mode = mode
        self.auto = auto

    def resolve(self, scope):
        return self.command.resolve(scope)

class CommandSequence(object):
    def __init__(self):
        self.blocks = []

    def add_block(self, block):
        self.blocks.append((block, []))

    def add_branch(self, mainline, branch):
        self.blocks.append((mainline, branch))

    def resolve(self, scope):
        output = []
        resolve_block = lambda block: (block, block.resolve(scope))
        for main, branch in self.blocks:
            output.append((resolve_block(main), map(resolve_block, branch)))
        return output

class Ref:
    pass

class Var(Ref):
    def __init__(self, nameref, *args):
        self.name = nameref
        self.args = args

    def resolve(self, scope):
        return scope.variable(self.name, self.args)

class Mem(Ref):
    def __init__(self, loc):
        self.loc = loc

    def resolve(self, scope):
        return '0x%04x' % scope.memory(self.loc)
class Command:

    def select(self, selector, scope, **kwargs):
        output = '@' + selector
        if 'selectors' in dir(self):
            for sel in self.selectors:
                kwargs.update(sel.resolve(scope))
        if not kwargs:
            return output
        output += '['
        for key,value in kwargs.items():
            output += '%s=%s,' % (key, str(value))
        output = output[:len(output)-1] + ']'
        return output

    def where(self, clause):
        if not 'selectors' in dir(self):
            self.selectors = []
        self.selectors.append(clause)
        return self

class Cmd(Command):
    def __init__(self, cmd):
        self.command = cmd

    def resolve(self, scope):
        cmd = self.command
        while True:
            idx = cmd.find('$')
            if idx == -1:
                break
            idx2 = cmd.find(':', idx)
            if idx2 == -1:
                break
            idx3 = cmd.find('$', idx2)
            if idx3 == -1:
                break
            param = cmd[idx+1:idx2]
            val = cmd[idx2+1:idx3]
            cmd = cmd[:idx] + scope.cmd_arg(param, val) + cmd[idx3+1:]
        return cmd

class Execute(Command):
    def __init__(self, where, cmd):
        self.command = cmd
        self.where = where

    def resolve(self, scope):
        selector = self.select('e', scope, tag=scope.entity_tag,
                               **self.where.resolve(scope))
        return 'execute %s ~ ~ ~ %s' % (selector, self.command.resolve(scope))

class Scoreboard(Command):
    def __init__(self, varref, value):
        assert isinstance(varref, Ref)
        assert isinstance(value, int)
        self.var = varref
        self.value = value

    def resolve(self, scope):
        return 'scoreboard players %s %s %s %d' % (
            self.op, self.select('e', scope, tag=scope.entity_tag),
            self.var.resolve(scope), self.value)

class SetConst(Scoreboard):
    op = 'set'

class AddConst(Scoreboard):
    op = 'add'

class RemConst(Scoreboard):
    op = 'remove'

class InRange(Scoreboard):
    def __init__(self, varref, min, max=None):
        self.var = varref
        self.min = min
        self.max = ' %d' % max if max is not None else ''

    def resolve(self, scope):
        return 'scoreboard players test %s %s %d%s' % (
            self.select('e', scope, tag=scope.entity_tag),
            self.var.resolve(scope), self.min, self.max)

class Tag(Scoreboard):
    def __init__(self, tag, op='add'):
        self.tag = tag
        self.op = op

    def resolve(self, scope):
        return 'scoreboard players tag %s %s %s' % (
            self.select('e', scope, tag=scope.entity_tag), self.op, self.tag)


class Operation(Command):
    def __init__(self, left, right):
        assert isinstance(left, Ref)
        assert isinstance(right, Ref)
        self.left = left
        self.right = right

    def resolve(self, scope):
        selector = self.select('e', scope, tag=scope.entity_tag)
        return 'scoreboard players operation %s %s %s %s %s' % (
            selector, self.left.resolve(scope), self.op,
            selector, self.right.resolve(scope))


class OpAssign(Operation): op = '='
class OpAdd(Operation): op = '+='
class OpSub(Operation): op = '-='
class OpMul(Operation): op = '*='
class OpDiv(Operation): op = '/='
class OpMod(Operation): op = '%='
class OpIfLt(Operation): op = '<'
class OpIfGt(Operation): op = '>'
class OpSwap(Operation): op = '><'

class Selector(object):
    pass

class SelRange(Selector):
    def __init__(self, varref, min=None, max=None):
        assert min is not None or max is not None
        assert isinstance(varref, Ref)
        self.var = varref
        self.min = min
        self.max = max

    def resolve(self, scope):
        name = self.var.resolve(scope)
        sel = {}
        if self.min is not None:
            sel['score_%s_min' % name] = self.min
        if self.max is not None:
            sel['score_%s' % name] = self.max
        return sel

class SelEquals(SelRange):
    def __init__(self, varref, value):
        super(SelEquals, self).__init__(varref, value, value)


class LabelledSequence(CommandSequence):
    def __init__(self, label, varname='func_pointer'):
        super(LabelledSequence, self).__init__()
        self.label = label

        cmd = Execute(where=SelEquals(Var(varname), label),
                cmd=SetConst(Var(varname), -1))

        self.add_block(CommandBlock(cmd, conditional=False, mode='REPEAT',
                                    auto=True))
