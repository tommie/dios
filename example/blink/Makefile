# #v(index) inside a macro causes "Symbol index not assigned a value."
# --mpasm-compatible should fix that, in at least v1.5.0.
AS = gpasm --mpasm-compatible
LD = gplink --mplink-compatible
DIOSGEN = ../../diosgen.py

ASFLAGS = -p p16f887 -r dec
LDFLAGS = -m

.PHONY: all
all: blink.hex

.PHONY: clean
clean:
	rm -f *.hex *.lst *.cod
	rm -f *.o

blink.hex: blink.main.o

%.cod: %.main.hex
%.lst: %.main.hex
%.hex: %.main.o
	$(LD) $(LDFLAGS) -o $@ $^

%.main.asm: %.asm
	$(DIOSGEN) -o $@ $<

%.o: %.asm *.inc
	$(AS) $(ASFLAGS) -c -o $@ $<
