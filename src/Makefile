all: smscript mkplan

smscript: smscript.cc
	$(CXX) -o smscript smscript.cc `pkg-config --cflags --libs spectmorph glib-2.0`

mkplan: mkplan.cc
	$(CXX) -o mkplan mkplan.cc `pkg-config --cflags --libs spectmorph glib-2.0`
