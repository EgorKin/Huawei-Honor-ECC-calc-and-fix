import bchlib
import hashlib
import os
import random
import struct, sys, argparse


# Регистр сдвига с линейной обратной связью (РСЛОС, англ. linear feedback shift register, LFSR)


def parity_lfsr_shift(din):
    global lfsr_poly
    global lfsr_value
    global lfsr_len
    
    feedback = lfsr_value[lfsr_len - 1] ^ din

    for i in range(lfsr_len-1, 0, -1):
        lfsr_value[i] = (feedback & lfsr_poly[i]) ^ lfsr_value[i-1]

    lfsr_value[0] = (feedback & lfsr_poly[0])


def get_parity(parity):
    global lfsr_value
    global lfsr_len

    shift = 0
    value = 0
    n = 0

    for i in range(lfsr_len-1, -1, -1):
        value |= (lfsr_value[i] << shift) & 255
        shift+=1
        if shift == 8:
            #*parity = value;
            #parity++; // переходим к след. символу
            parity[n] = value
            n+=1
            shift = 0
            value = 0

    return parity


def strtolfsr(lfsr, value):
    length = len(value);

    for i in range(0, length):
        c = value[length - 1 - i] # идем от конца текстового битового предстваления полинома poly
        if(c == '1'):
            lfsr[i] = 1 # а пишем 1 или 0 идя с начала другого массива
        else:
            lfsr[i] = 0

    return lfsr


def inttolfsr(lfsr, value):
    for i in range(0, lfsr_len):
        if (value & (1 << i)):
            lfsr[i] = 1
        else:
            lfsr[i] = 0

    return lfsr


def ecc_parity_gen(data, bits, ecc_level, ecc_code):
    global lfsr_poly
    global lfsr_value
    global lfsr_len

    #lfsr_init(14*8, "b1111111001111011100101111111111001010011100001000011110001110110010110011110001001110011110011010101110000101101", 0);
    lfsr_len = 14*8
    poly = "1111111001111011100101111111111001010011100001000011110001110110010110011110001001110011110011010101110000101101"
    value = 0

	#memset(lfsr_poly, 0x00, 2048)
    for i in range(2048):
        lfsr_poly[ i ] = 0x00

    #memset(lfsr_value, 0x00, 2048)
    for i in range(2048):
        lfsr_value[ i ] = 0x00

    lfsr_poly = strtolfsr(lfsr_poly, poly) # lfsr_poly = poly только пройденному с конца к началу
    lfsr_value = inttolfsr(lfsr_value, value) # value = 0 у нас поэтому lfsr_value = 0 тоже

    for i in range(0,bits): # bits для нас = 1040*8
        c = data[i >> 3]
        c = (c >> (i & 0x7)) & 0x1 # берем с младшего бита до старшего
        parity_lfsr_shift(c) # если считаем ECC для FF FF FF... то с = 1 всегда

    ecc_code = get_parity(ecc_code)

    return ecc_code


def ecc_data_gen(data, len):
    for i in range(0, len):
        data[i] = ~data[i] & 255

    return data


def ecc_4bit_gen(data, len, ecc_code):
    data = ecc_data_gen(data, len) # инвертируем len байт в массиве data
    ecc_code = ecc_parity_gen(data, len*8, 8, ecc_code)
    for i in range(0,14):
        ecc_code[i] = ~ecc_code[i] & 255

    return ecc_code



#typedef struct {
#    byte data1[1040] <bgcolor=0x888800>; // 1040 data bytes for ECC1 calc
#    byte ECC1[14] <bgcolor=0xffff00>;
#
#    byte data20[994] <bgcolor=0x008888>;
#    byte BadBlockMarker[2] <bgcolor=0x0000ff>;
#    byte data21[14] <bgcolor=0x008888>;
#    byte ECC2[14] <bgcolor=0xffff00>;
#    byte data22_oobfree[30] <bgcolor=0x00ffff>; // 994(data_first)+14(data_last)+2(BBM)+30(oobfree) = 1040 data bytes for ECC2 calc
#
#    byte erasedFF[4];
#} Data_t;

def ECC_calc_for_page(in_offset):
    global ecc1_buf
    global ecc2_buf

    fin = open(input_file, 'rb')
    fin.seek(in_offset, 0)


    # посчитаем ECC1
    buf = []
    for i in range(1040):
        buf.append(struct.unpack('B', fin.read(1))[0]) # 1040 байт данных для расчета ECC1

    # ECC1[14] считанная из дампа
    ECC1 = fin.read(14)

    ecc1_buf = ecc_4bit_gen(buf, 1040, ecc1_buf) # 1040 = 0x410 , в ecc_buf будет расчитаная и проинвертированная ECC по инвертированным побайтно данным в buf длиной в 0x410 байт



    # ECC1 из дампа
    print("ECC1_read = ", end='')
    for i in range(14):
        print("%02X " % ECC1[i], end='')
    print("")

    # ECC1 вычисленая нами
    print("ECC1_calc = ", end='')
    for i in range(14):
        print("%02X " % ecc1_buf[i], end='')
    print("")

    # покажем разницу между расчитаной и считаной из дампа ECC1
    print("ECC1_XOR  = ", end='')
    for i in range(14):
        xor = int(ECC1[i]) ^ ecc1_buf[i]
        if xor&0xF0 == 0:
            print("%01X" % (xor>>4), end='')
        else:
            print("\033[91m%01X\033[0m" % (xor>>4), end='')
        if xor&0x0F == 0:
            print("%01X " % (xor&0xF), end='')
        else:
            print("\033[91m%01X\033[0m " % (xor&0xF), end='')
    print("")
    # ECC1 = 0A 3A E9 39 43 DE 09 AC 83 22 D0 E1 7F F3
    
    
    # посчитаем ECC2
    buf2 = []

    # data2.0[994]
    for i in range(994):
        buf2.append(struct.unpack('B', fin.read(1))[0])

    # BadBlockMarker[2]
    BBM = []
    BBM.append(struct.unpack('B', fin.read(1))[0])
    BBM.append(struct.unpack('B', fin.read(1))[0])

    # data2.1[14]
    for i in range(14):
        buf2.append(struct.unpack('B', fin.read(1))[0])

    # ECC2[14] считаная из дампа
    ECC2 = fin.read(14)

    # + BBM (FF FF)
    buf2.append(BBM[0])
    buf2.append(BBM[1])

    # data2.2_oobfree[30] (FF*30)
    for i in range(30):
        buf2.append(struct.unpack('B', fin.read(1))[0])
    
    # erasedFF[4] - осталось до конца страницы считать, но можно не считывать
    #erased = []
    #for i in range(4):
    #   erased.append(struct.unpack('B', fin.read(1))[0])
    
    # 994(data_first)+14(data_last)+2(BBM)+30(oobfree) = 1040 байт данных для расчета ECC2
    ecc2_buf = ecc_4bit_gen(buf2, 1040, ecc2_buf) # 1040 = 0x410 , в ecc_buf будет расчитаная и проинвертированная ECC по инвертированным побайтно данным в buf длиной в 0x410 байт
    
    
    # ECC2 из дампа
    print("ECC2_read = ", end='')
    for i in range(14):
        print("%02X " % ECC2[i], end='')
    print("")

    # ECC2 вычисленая нами
    print("ECC2_calc = ", end='')
    for i in range(14):
        print("%02X " % ecc2_buf[i], end='')
    print("")

    # покажем разницу между расчитаной и считаной из дампа ECC2
    print("ECC2_XOR  = ", end='')
    for i in range(14):
        xor = int(ECC2[i]) ^ ecc2_buf[i]
        if xor&0xF0 == 0:
            print("%01X" % (xor>>4), end='')
        else:
            print("\033[91m%01X\033[0m" % (xor>>4), end='')
        if xor&0x0F == 0:
            print("%01X " % (xor&0xF), end='')
        else:
            print("\033[91m%01X\033[0m " % (xor&0xF), end='')
    print("")
    # ECC2 = 79 E8 94 34 A2 D6 B8 41 11 95 93 4B 6B 5B
    
    fin.close()
    
    return ecc1_buf, ecc2_buf


in_file = ''

lfsr_poly = []
for i in range(2048):
    lfsr_poly.append(0x00)

lfsr_value = []
for i in range(2048):
    lfsr_value.append(0x00)

lfsr_len = 112

#memset(ecc_buf, 0xFF, sizeof(ecc_buf)); # проинициализировали массив под ECC всеми FF
ecc1_buf = []
for i in range(14):
    ecc1_buf.append(0xff)

ecc2_buf = []
for i in range(14):
    ecc2_buf.append(0xff)


def get_args():
    global input_file
    
    p = argparse.ArgumentParser()
    p.add_argument('-i',metavar='filename', nargs=1, help='input file')
    
    if len(sys.argv) < 3:
        p.print_help(sys.stderr)
        sys.exit(1)

    args = p.parse_args(sys.argv[1:])
    input_file = args.i[0]
    print(in_file)



def main():
    get_args()
    
    #ECC_calc_for_page(0x22080) # incorrect ECC1 1 bit
    #ECC_calc_for_page(0x1CE00) # 2 bit-flip errors
    #ECC_calc_for_page(0x207c0) # incorrect ECC1 last byte(1 bit)
    
    ECC_calc_for_page(0x840 * 22)
    
    



if __name__ == "__main__":
    main()

