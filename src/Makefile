PROGS = smscript mkplan

all: $(PROGS)

smscript: smscript.cc
	$(CXX) -o smscript smscript.cc `pkg-config --cflags --libs spectmorph glib-2.0` -O2 -Wall

mkplan: mkplan.cc
	$(CXX) -o mkplan mkplan.cc `pkg-config --cflags --libs spectmorph glib-2.0` -O2 -Wall

clean:
	rm -f $(PROGS)
