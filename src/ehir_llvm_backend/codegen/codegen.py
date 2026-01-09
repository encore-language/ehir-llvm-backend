import llvmlite.binding as llvm
import llvmlite.ir as ir
from ehir.core.block import TerminatedBlock
from ehir.core.derectives import Derective_fn, Derective_struct
from ehir.core.derectives.base import Derective
from ehir.core.instructions.base import Instruction
from ehir.core.instructions.control_flow.ret import Instruction_ret
from ehir.core.instructions.control_flow.switch import Instruction_switch
from ehir.core.instructions.memory import (
    Instruction_getfieldptr,
    Instruction_getptr,
    Instruction_hfree,
    Instruction_pcast,
    Instruction_put,
    Instruction_store,
)
from ehir.core.instructions.memory.halloc import Instruction_halloc
from ehir.core.instructions.memory.load import Instruction_load
from ehir.core.instructions.memory.salloc import Instruction_salloc
from ehir.core.instructions.operators.arithmetic import (
    Instruction_add,
    Instruction_div,
    Instruction_mul,
    Instruction_sub,
)
from ehir.core.instructions.operators.logic import Instruction_and, Instruction_ieq, Instruction_neq, Instruction_or
from ehir.core.instructions.special import Instruction_comment
from ehir.core.instructions.special.call import Instruction_call
from ehir.core.primitives import Usize, Usize_t
from ehir.core.primitives.base import Primitive
from ehir.core.type import Pointer, Type
from ehir.postprocessor import ProcessedModule


class Codegen:
    builder: ir.IRBuilder
    module: ir.Module

    def __init__(self):
        llvm.initialize_native_target()
        llvm.initialize_native_asmprinter()
        llvm.initialize_native_asmparser()

        self.module = ir.Module()
        self.builder = ir.IRBuilder()
        self._variables: dict[str, object] = {}
        self._structs: dict[str, ir.LiteralStructType] = {}

    def run(self, mod: ProcessedModule) -> ir.Module:
        for derective in mod.structs:
            self._codegen_struct_decl(derective)

        for derective in mod.structs:
            self._codegen_struct_body(derective)

        for derective in mod.funcs:
            self._codegen_fn_decl(derective)

        try:
            for derective in mod.funcs:
                self._codegen_fn_body(derective)
        except Exception as e:
            print(self.module)
            raise e

        return self.module

    def _codegen_struct_decl(self, struct: Derective_struct):
        st = ir.LiteralStructType([])
        if struct.name in self._structs:
            raise ValueError(f"Struct '{struct.name}' already declared")
        self._structs[struct.name] = st

    def _codegen_fn_decl(self, fn: Derective_fn):
        ret_type = self._build_type(fn.ret_type)
        param_types = [self._build_type(t.type) for t in fn.params]

        func_type = ir.FunctionType(ret_type, param_types)
        func = ir.Function(self.module, func_type, name=fn.name)

        for i, param in enumerate(func.args):
            param.name = fn.params[i].name

        return func

    def _codegen_derective(self, derective: Derective):
        if isinstance(derective, Derective_fn):
            self._codegen_fn_body(derective)
        elif isinstance(derective, Derective_struct):
            self._codegen_struct_body(derective)
        else:
            raise NotImplementedError(f"Unsupported derective type: {type(derective)}")

    def _codegen_struct_body(self, struct: Derective_struct):
        struct_type = self._structs[struct.name]
        field_types = [self._build_type(param.type) for param in struct.params]
        struct_type.elements = field_types

    def _codegen_fn_body(self, fn: Derective_fn):
        func = [f for f in self.module.functions if f.name == fn.name][0]

        self._variables.clear()
        for i, param in enumerate(func.args):
            param_name = fn.params[i].name
            self._variables[param_name] = param
            param.name = param_name

        ir_blocks = []
        for block in fn.get_body():
            assert isinstance(block, TerminatedBlock)
            ir_block = func.append_basic_block(block.name)
            ir_blocks.append(ir_block)

        for block, ir_block in zip(fn.get_body(), ir_blocks, strict=True):
            assert block.name == ir_block.name
            self.builder.position_at_end(ir_block)
            self._build_block(block)

    def _build_block(self, block: TerminatedBlock):
        for instr in block.body:
            self._build_instruction(instr)
        self._build_instruction(block.term)

    def _build_instruction(self, instr: Instruction):
        if isinstance(instr, Instruction_salloc):
            self._build_salloc(instr)
        elif isinstance(instr, Instruction_halloc):
            self._build_halloc(instr)
        elif isinstance(instr, Instruction_put):
            self._build_put(instr)
        elif isinstance(instr, Instruction_load):
            self._build_load(instr)
        elif isinstance(instr, Instruction_ret):
            self._build_ret(instr)
        elif isinstance(instr, Instruction_add):
            self._build_add(instr)
        elif isinstance(instr, Instruction_sub):
            self._build_sub(instr)
        elif isinstance(instr, Instruction_or):
            self._build_or(instr)
        elif isinstance(instr, Instruction_and):
            self._build_and(instr)
        elif isinstance(instr, Instruction_ieq):
            self._build_ieq(instr)
        elif isinstance(instr, Instruction_neq):
            self._build_neq(instr)
        elif isinstance(instr, Instruction_mul):
            self._build_mul(instr)
        elif isinstance(instr, Instruction_div):
            self._build_div(instr)
        elif isinstance(instr, Instruction_call):
            self._build_call(instr)
        elif isinstance(instr, Instruction_switch):
            self._build_switch(instr)
        elif isinstance(instr, Instruction_hfree):
            self._build_hfree(instr)
        elif isinstance(instr, Instruction_store):
            self._build_store(instr)
        elif isinstance(instr, Instruction_pcast):
            self._build_pcast(instr)
        elif isinstance(instr, Instruction_getfieldptr):
            self._build_getfieldptr(instr)
        elif isinstance(instr, Instruction_getptr):
            self._build_getptr(instr)
        elif isinstance(instr, Instruction_comment):
            pass  # skip comment
        else:
            raise NotImplementedError(f"Unsupported instruction type: {type(instr)}")

    def _build_getptr(self, instr: Instruction_getptr):
        self.builder.comment("")
        self.builder.comment(f"{instr}")

        assert instr.var.type is not None
        type = self._build_type(instr.var.type)
        ptr = self.builder.alloca(type, name=instr.var.name)
        self._variables[instr.var.name] = ptr

    def _build_getptr(self, instr: Instruction_getptr):
        self.builder.comment("")
        self.builder.comment(f"{instr}")

        assert instr.var.type is not None
        dst_type = self._build_type(instr.var.type)

        alloca = self.builder.alloca(dst_type, name=instr.var_out.name)
        self.builder.store(self._variables[instr.var.name], alloca)
        self._variables[instr.var_out.name] = alloca

    def _build_pcast(self, instr: Instruction_pcast):
        self.builder.comment("")
        self.builder.comment(f"{instr}")

        value = self._variables[instr.var.name]
        assert hasattr(value, "type")
        src_type = value.type

        assert instr.var.type is not None
        dst_type = self._build_type(instr.type)

        # Cast
        ## Same
        if src_type == dst_type:
            return

        result = None
        ## Int to Int
        if isinstance(src_type, ir.IntType) and isinstance(dst_type, ir.IntType):
            src_width = src_type.width
            dst_width = dst_type.width

            if src_width < dst_width:
                result = self.builder.zext(value, dst_type, name=instr.var_out.name)
            elif src_width > dst_width:
                result = self.builder.trunc(value, dst_type, name=instr.var_out.name)
            else:
                raise RuntimeError("Unreachable")

        else:
            raise NotImplementedError(f"Unsupported cast: {src_type} -> {dst_type}")

        self._variables[instr.var_out.name] = result
        return result

    def _build_store(self, instr: Instruction_store):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        value = self._variables[instr.var_src.name]
        ptr = self._variables[instr.var_dst.name]
        self.builder.store(value, ptr)

    def _build_getfieldptr(self, instr: Instruction_getfieldptr):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        base = self._variables[instr.src.name]
        assert hasattr(base, "type")
        if not isinstance(base.type, ir.PointerType):
            temp = self.builder.alloca(base.type)
            self.builder.store(base, temp)
            base = temp

        indices = [ir.Constant(ir.IntType(32), 0)]
        for idx_var in instr.indexes:
            indices.append(ir.Constant(ir.IntType(32), int(idx_var.name)))

        result = self.builder.gep(base, indices, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_salloc(self, instr: Instruction_salloc):
        self.builder.comment("")
        self.builder.comment(f"{instr}")

        byte_size = self._sizeof(instr.type)
        ptr = self.builder.alloca(ir.IntType(8), size=byte_size, name=f".salloc_{instr.var_out.name}")
        target_type = self._build_type(instr.type)
        casted_ptr = self.builder.bitcast(ptr, ir.PointerType(target_type), name=instr.var_out.name)
        self._variables[instr.var_out.name] = casted_ptr
        return casted_ptr

    def _build_halloc(self, instr: Instruction_halloc):
        self.builder.comment("")
        self.builder.comment(f"{instr}")

        byte_size = self._sizeof(instr.type)
        malloc_func = self._get_malloc_function()
        raw_ptr = self.builder.call(malloc_func, [byte_size], name=f".halloc_{instr.var_out.name}")
        target_type = self._build_type(instr.type)
        casted_ptr = self.builder.bitcast(raw_ptr, ir.PointerType(target_type), name=instr.var_out.name)
        self._variables[instr.var_out.name] = casted_ptr
        return casted_ptr

    def _build_hfree(self, instr: Instruction_hfree):
        self.builder.comment("")
        self.builder.comment(f"{instr}")

        ptr = self._variables[instr.var.name]
        free_func = self._get_free_function()
        dst_type = free_func.args[0].type
        ptr_conv = self.builder.bitcast(typ=dst_type, val=ptr)

        self.builder.call(free_func, [ptr_conv])

    def _build_put(self, instr: Instruction_put):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        constant = self._build_primitive(instr.primitive)
        self.builder.store(constant, self._variables[instr.var.name])

    def _build_load(self, instr: Instruction_load):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        ptr = self._variables[instr.var.name]
        value = self.builder.load(ptr, name=instr.var_out.name)
        self._variables[instr.var_out.name] = value
        return value

    def _build_add(self, instr: Instruction_add):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.add(left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_sub(self, instr: Instruction_sub):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.sub(left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_mul(self, instr: Instruction_mul):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.mul(left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_div(self, instr: Instruction_div):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.sdiv(left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_or(self, instr: Instruction_or):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.or_(left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_and(self, instr: Instruction_and):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.and_(left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_ieq(self, instr: Instruction_ieq):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.icmp_signed("==", left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_neq(self, instr: Instruction_neq):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        left = self._variables[instr.lhs.name]
        right = self._variables[instr.rhs.name]
        result = self.builder.icmp_signed("!=", left, right, name=instr.var_out.name)
        self._variables[instr.var_out.name] = result
        return result

    def _build_call(self, instr: Instruction_call):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        func = [f for f in self.module.functions if f.name == instr.fn_name][0]

        args = [self._variables[arg.name] for arg in instr.args]
        result = self.builder.call(func, args)
        self._variables[instr.var_out.name] = result
        return result

    def _build_switch(self, instr: Instruction_switch):
        self.builder.comment("")
        self.builder.comment("switch")
        cond_value = self._variables[instr.cond_var.name]

        blocks_mapping: dict[str, ir.Block] = {}
        for ir_block in self.builder.function.blocks:
            blocks_mapping[ir_block.name] = ir_block

        default_block = blocks_mapping[instr.default_case]
        switch = self.builder.switch(cond_value, default_block)
        for case_value, block_name in instr.cases:
            const_val = self._build_primitive(case_value)
            target_block = blocks_mapping[block_name]
            switch.add_case(const_val, target_block)

    def _build_ret(self, instr: Instruction_ret):
        self.builder.comment("")
        self.builder.comment(f"{instr}")
        value = self._variables[instr.var.name]
        self.builder.ret(value)

    def _build_type(self, type: Type) -> ir.Type:
        if isinstance(type, Pointer):
            return ir.PointerType(self._build_type(type.pointee))

        if isinstance(type, Usize_t):
            return ir.IntType(bits=type.size)

        if type.name not in self._structs:
            raise ValueError(f"Struct '{type.name}' not found")
        struct = self._structs[type.name]

        if isinstance(type, Pointer):
            return ir.PointerType(struct)

        return struct

    def _build_primitive(self, prim: Primitive) -> ir.Constant:
        if isinstance(prim, Usize):
            return ir.Constant(ir.IntType(bits=prim.type.size), prim.val)
        raise NotImplementedError(f"Unsupported primitive: {prim}")

    def _sizeof(self, type: Type):
        t = self._build_type(type)
        null_ptr_type = ir.PointerType(t)
        null_ptr = ir.Constant(null_ptr_type, None)
        one = ir.Constant(ir.IntType(32), 1)
        size_ptr = self.builder.gep(null_ptr, [one], name=f".sizeof_{type.name}_ptr")
        return self.builder.ptrtoint(size_ptr, ir.IntType(64), name=f".sizeof_{type.name}_")

    def _get_malloc_function(self) -> ir.Function:
        if "malloc" in self.module.globals:
            return self.module.globals["malloc"]
        malloc_type = ir.FunctionType(
            ir.IntType(8).as_pointer(),
            [ir.IntType(64)],
        )

        malloc_func = ir.Function(self.module, malloc_type, name="malloc")
        malloc_func.attributes.add("noinline")
        return malloc_func

    def _get_free_function(self):
        if "free" in self.module.globals:
            return self.module.globals["free"]

        free_type = ir.FunctionType(ir.VoidType(), [ir.IntType(8).as_pointer()])
        free_func = ir.Function(self.module, free_type, name="free")
        free_func.attributes.add("noinline")
        return free_func

    def _initialize_memory(self, ptr, elem_type, size):
        memset_func = self._get_memset_function()
        byte_ptr = self.builder.bitcast(ptr, ir.IntType(8).as_pointer())
        zero = ir.Constant(ir.IntType(8), 0)
        self.builder.call(memset_func, [byte_ptr, zero, size])

    def _get_memset_function(self):
        if "memset" in self.module.globals:
            return self.module.globals["memset"]

        memset_type = ir.FunctionType(
            ir.IntType(8).as_pointer(),
            [
                ir.IntType(8).as_pointer(),
                ir.IntType(32),
                ir.IntType(64),
            ],
        )

        memset_func = ir.Function(self.module, memset_type, name="memset")
        memset_func.attributes.add("noinline")
        return memset_func
