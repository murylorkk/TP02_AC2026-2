# Murilo Duarte Bittencourt
# 22400544

import sys
import re

ABI_MAP = {
    "zero": "x0", "ra": "x1", "sp": "x2", "gp": "x3", "tp": "x4",
    "t0": "x5", "t1": "x6", "t2": "x7", "s0": "x8", "fp": "x8", "s1": "x9",
    "a0": "x10", "a1": "x11", "a2": "x12", "a3": "x13", "a4": "x14",
    "a5": "x15", "a6": "x16", "a7": "x17", "s2": "x18", "s3": "x19",
    "s4": "x20", "s5": "x21", "s6": "x22", "s7": "x23", "s8": "x24",
    "s9": "x25", "s10": "x26", "s11": "x27", "t3": "x28", "t4": "x29",
    "t5": "x30", "t6": "x31"
}

def reg_canonico(reg_str):
    reg_clean = reg_str.strip().lower()
    if reg_clean in ABI_MAP:
        return ABI_MAP[reg_clean]
    return reg_clean # assume que já é x0..x31 caso não estiver no mapa 

registradores = {f"x{i}": 0 for i in range(32)}

def get_reg(reg_name):
    return registradores[reg_canonico(reg_name)]

def set_reg(reg_name, val):
    canon = reg_canonico(reg_name)
    if canon != "x0":
        val = val & 0xFFFFFFFF
        if val >= 0x80000000:
            val -= 0x100000000
        registradores[canon] = val

memoria = {}

def write_byte(addr, val):
    memoria[addr] = val & 0xFF

def read_byte(addr):
    b = memoria.get(addr, 0) & 0xFF
    return b - 0x100 if b >= 0x80 else b # Extensão de sinal

def write_half(addr, val):
    val = val & 0xFFFF
    memoria[addr] = val & 0xFF
    memoria[addr + 1] = (val >> 8) & 0xFF

def read_half(addr):
    b0 = memoria.get(addr, 0) & 0xFF
    b1 = memoria.get(addr + 1, 0) & 0xFF
    val = b0 | (b1 << 8)
    return val - 0x10000 if val >= 0x8000 else val

def write_word(addr, val):
    val = val & 0xFFFFFFFF
    memoria[addr] = val & 0xFF
    memoria[addr + 1] = (val >> 8) & 0xFF
    memoria[addr + 2] = (val >> 16) & 0xFF
    memoria[addr + 3] = (val >> 24) & 0xFF

def read_word(addr):
    b0 = memoria.get(addr, 0) & 0xFF
    b1 = memoria.get(addr + 1, 0) & 0xFF
    b2 = memoria.get(addr + 2, 0) & 0xFF
    b3 = memoria.get(addr + 3, 0) & 0xFF
    val = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
    return val - 0x100000000 if val >= 0x80000000 else val

rotulos = {}
instrucoes = {}

def parse_mem_operand(op_str):
    match = re.match(r'^([^\(]*)\(([^)]+)\)$', op_str.strip())
    if match:
        offset = int(match.group(1).strip(), 0) if match.group(1).strip() else 0
        return offset, match.group(2).strip()
    raise ValueError(f"Operando de memória inválido: {op_str}")

def carregar_programa(caminho_arquivo):
    text_addr = 0x00000000
    data_addr = 0x00200000
    segmento_atual = ".text"

    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        linhas = f.readlines()

    for linha in linhas:
        linha = linha.split("#")[0].strip()
        if not linha: continue

        if ":" in linha:
            partes = linha.split(":", 1)
            nome_rotulo = partes[0].strip()
            rotulos[nome_rotulo] = text_addr if segmento_atual == ".text" else data_addr
            linha = partes[1].strip()

        if not linha: continue

        if linha.startswith("."):
            partes = linha.split(maxsplit=1)
            diretiva = partes[0].lower()
            args = partes[1].strip() if len(partes) > 1 else ""

            if diretiva == ".text": segmento_atual = ".text"
            elif diretiva == ".data": segmento_atual = ".data"
            elif diretiva == ".align":
                alinhamento = 1 << int(args)
                if segmento_atual == ".data" and data_addr % alinhamento != 0:
                    data_addr += alinhamento - (data_addr % alinhamento)
            elif diretiva == ".word":
                for v in [int(v.strip(), 0) for v in args.split(",")]:
                    write_word(data_addr, v); data_addr += 4
            elif diretiva == ".half":
                for v in [int(v.strip(), 0) for v in args.split(",")]:
                    write_half(data_addr, v); data_addr += 2
            elif diretiva == ".byte":
                for v in [int(v.strip(), 0) for v in args.split(",")]:
                    write_byte(data_addr, v); data_addr += 1
            elif diretiva in [".zero", ".space"]:
                data_addr += int(args)
        else:
            partes = linha.split(None, 1)
            mnemonico = partes[0].lower()
            operandos = [op.strip() for op in partes[1].split(",")] if len(partes) > 1 else []
            instrucoes[text_addr] = [mnemonico] + operandos
            text_addr += 4

def executar_emulador():
    if "main" not in rotulos:
        sys.stderr.write("erro: rótulo 'main' não encontrado.\n")
        sys.exit(1)

    pc = rotulos["main"]

    while pc in instrucoes:
        campos = instrucoes[pc]
        mnem = campos[0]
        pc_alterado = False

        # loads
        if mnem == "la":
            set_reg(campos[1], rotulos[campos[2]])
        elif mnem == "li":
            set_reg(campos[1], int(campos[2], 0))
        elif mnem == "lb":
            offset, rs1 = parse_mem_operand(campos[2])
            set_reg(campos[1], read_byte(get_reg(rs1) + offset))
        elif mnem == "lbu":
            offset, rs1 = parse_mem_operand(campos[2])
            b = memoria.get(get_reg(rs1) + offset, 0) & 0xFF
            set_reg(campos[1], b)
        elif mnem == "lh":
            offset, rs1 = parse_mem_operand(campos[2])
            set_reg(campos[1], read_half(get_reg(rs1) + offset))
        elif mnem == "lhu":
            offset, rs1 = parse_mem_operand(campos[2])
            b0 = memoria.get(get_reg(rs1) + offset, 0) & 0xFF
            b1 = memoria.get(get_reg(rs1) + offset + 1, 0) & 0xFF
            set_reg(campos[1], b0 | (b1 << 8))
        elif mnem == "lw":
            offset, rs1 = parse_mem_operand(campos[2])
            set_reg(campos[1], read_word(get_reg(rs1) + offset))

        # stores
        elif mnem == "sb":
            offset, rs1 = parse_mem_operand(campos[2])
            write_byte(get_reg(rs1) + offset, get_reg(campos[1]))
        elif mnem == "sh":
            offset, rs1 = parse_mem_operand(campos[2])
            write_half(get_reg(rs1) + offset, get_reg(campos[1]))
        elif mnem == "sw":
            offset, rs1 = parse_mem_operand(campos[2])
            write_word(get_reg(rs1) + offset, get_reg(campos[1]))

        # aritmética e lógica (R-type)
        elif mnem == "add":
            set_reg(campos[1], get_reg(campos[2]) + get_reg(campos[3]))
        elif mnem == "sub":
            set_reg(campos[1], get_reg(campos[2]) - get_reg(campos[3]))
        elif mnem == "sll":
            set_reg(campos[1], get_reg(campos[2]) << (get_reg(campos[3]) & 0x1F))
        elif mnem == "slt":
            set_reg(campos[1], 1 if get_reg(campos[2]) < get_reg(campos[3]) else 0)
        elif mnem == "sltu":
            u_rs1 = get_reg(campos[2]) & 0xFFFFFFFF
            u_rs2 = get_reg(campos[3]) & 0xFFFFFFFF
            set_reg(campos[1], 1 if u_rs1 < u_rs2 else 0)
        elif mnem == "xor":
            set_reg(campos[1], get_reg(campos[2]) ^ get_reg(campos[3]))
        elif mnem == "srl":
            u_rs1 = get_reg(campos[2]) & 0xFFFFFFFF
            set_reg(campos[1], u_rs1 >> (get_reg(campos[3]) & 0x1F))
        elif mnem == "sra":
            set_reg(campos[1], get_reg(campos[2]) >> (get_reg(campos[3]) & 0x1F))
        elif mnem == "or":
            set_reg(campos[1], get_reg(campos[2]) | get_reg(campos[3]))
        elif mnem == "and":
            set_reg(campos[1], get_reg(campos[2]) & get_reg(campos[3]))
        elif mnem == "mul":
            set_reg(campos[1], get_reg(campos[2]) * get_reg(campos[3]))
        elif mnem == "div":
            denom = get_reg(campos[3])
            set_reg(campos[1], int(get_reg(campos[2]) / denom) if denom != 0 else -1)
        elif mnem == "rem":
            denom = get_reg(campos[3])
            set_reg(campos[1], get_reg(campos[2]) % denom if denom != 0 else get_reg(campos[2]))

        # aritmética e lógica imediata(I-type) 
        elif mnem == "addi":
            set_reg(campos[1], get_reg(campos[2]) + int(campos[3], 0))
        elif mnem == "slti":
            set_reg(campos[1], 1 if get_reg(campos[2]) < int(campos[3], 0) else 0)
        elif mnem == "sltiu":
            u_rs1 = get_reg(campos[2]) & 0xFFFFFFFF
            u_imm = int(campos[3], 0) & 0xFFFFFFFF
            set_reg(campos[1], 1 if u_rs1 < u_imm else 0)
        elif mnem == "ori":
            set_reg(campos[1], get_reg(campos[2]) | int(campos[3], 0))
        elif mnem == "andi":
            set_reg(campos[1], get_reg(campos[2]) & int(campos[3], 0))
        elif mnem == "slli":
            set_reg(campos[1], get_reg(campos[2]) << (int(campos[3], 0) & 0x1F))
        elif mnem == "srli":
            u_rs1 = get_reg(campos[2]) & 0xFFFFFFFF
            set_reg(campos[1], u_rs1 >> (int(campos[3], 0) & 0x1F))
        elif mnem == "srai":
            set_reg(campos[1], get_reg(campos[2]) >> (int(campos[3], 0) & 0x1F))

        # desvios condicionais (B-type) 
        elif mnem == "beq":
            if get_reg(campos[1]) == get_reg(campos[2]):
                pc = rotulos[campos[3]]
                pc_alterado = True
        elif mnem == "bne":
            if get_reg(campos[1]) != get_reg(campos[2]):
                pc = rotulos[campos[3]]
                pc_alterado = True
        elif mnem == "blt":
            if get_reg(campos[1]) < get_reg(campos[2]):
                pc = rotulos[campos[3]]
                pc_alterado = True
        elif mnem == "bge":
            if get_reg(campos[1]) >= get_reg(campos[2]):
                pc = rotulos[campos[3]]
                pc_alterado = True
        elif mnem == "bltu":
            u_rs1 = get_reg(campos[1]) & 0xFFFFFFFF
            u_rs2 = get_reg(campos[2]) & 0xFFFFFFFF
            if u_rs1 < u_rs2:
                pc = rotulos[campos[3]]
                pc_alterado = True
        elif mnem == "bgeu":
            u_rs1 = get_reg(campos[1]) & 0xFFFFFFFF
            u_rs2 = get_reg(campos[2]) & 0xFFFFFFFF
            if u_rs1 >= u_rs2:
                pc = rotulos[campos[3]]
                pc_alterado = True

        # pseudoinstruções
        elif mnem == "mv":
            set_reg(campos[1], get_reg(campos[2]))
        elif mnem == "j":
            pc = rotulos[campos[1]]
            pc_alterado = True
        elif mnem == "jr":
            pc = get_reg(campos[1])
            pc_alterado = True

        # sistema 
        elif mnem == "ecall":
            servico = get_reg("a7")
            if servico == 1:
                print(get_reg("a0"), end="", flush=True)
            elif servico == 10:
                break

        if not pc_alterado:
            pc += 4

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: python emulador.py codigo.s")
        sys.exit(1)

    carregar_programa(sys.argv[1])
    executar_emulador()