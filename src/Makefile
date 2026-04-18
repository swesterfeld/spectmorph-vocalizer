PROGS = smscript mkplan mxmlparse

all: $(PROGS)

smscript: smscript.cc
	$(CXX) -o smscript smscript.cc `pkg-config --cflags --libs spectmorph glib-2.0` -O2 -Wall

mkplan: mkplan.cc
	$(CXX) -o mkplan mkplan.cc `pkg-config --cflags --libs spectmorph glib-2.0` -O2 -Wall

mxmlparse: mxmlparse.cc
	$(CXX) -o mxmlparse mxmlparse.cc -O2 -Wall

clean:
	rm -f $(PROGS)
