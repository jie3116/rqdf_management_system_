import 'package:intl/intl.dart';

class CurrencyFormatter {
  const CurrencyFormatter._();

  static final NumberFormat _rupiah = NumberFormat.currency(
    locale: 'id_ID',
    symbol: 'Rp ',
    decimalDigits: 0,
  );

  static String rupiah(num? value) {
    return _rupiah.format(value ?? 0);
  }
}
