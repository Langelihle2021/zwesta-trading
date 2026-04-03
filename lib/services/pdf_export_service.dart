import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import '../models/account.dart';
import '../models/statement.dart';

class PdfExportService {
  static Future<pw.Document> generateStatementPdf(
    Statement statement,
    Account account,
  ) async {
    final pdf = pw.Document();

    final dateFormat = DateFormat('MMMM dd, yyyy');
    final currencyFormat = NumberFormat.currency(symbol: '${account.currency} ');

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(40),
        build: (context) => [
          // Header
          pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            children: [
              pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
                children: [
                  pw.Column(
                    crossAxisAlignment: pw.CrossAxisAlignment.start,
                    children: [
                      pw.Text(
                        'ZWESTA TRADING',
                        style: pw.TextStyle(
                          fontSize: 24,
                          fontWeight: pw.FontWeight.bold,
                        ),
                      ),
                      pw.SizedBox(height: 4),
                      pw.Text(
                        'Trading Statement',
                        style: pw.TextStyle(
                          fontSize: 16,
                          fontWeight: pw.FontWeight.bold,
                          color: PdfColors.blue,
                        ),
                      ),
                    ],
                  ),
                  pw.Column(
                    crossAxisAlignment: pw.CrossAxisAlignment.end,
                    children: [
                      pw.Text(
                        'Statement Generated',
                        style: const pw.TextStyle(fontSize: 10),
                      ),
                      pw.Text(
                        dateFormat.format(statement.generatedAt),
                        style: pw.TextStyle(
                          fontSize: 12,
                          fontWeight: pw.FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              pw.Divider(height: 30),
            ],
          ),

          // Account Information Section
          pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            children: [
              pw.Text(
                'Account Information',
                style: pw.TextStyle(
                  fontSize: 14,
                  fontWeight: pw.FontWeight.bold,
                ),
              ),
              pw.SizedBox(height: 12),
              _buildAccountInfoTable(account, statement, dateFormat, currencyFormat),
              pw.SizedBox(height: 24),
            ],
          ),

          // Period Summary Section
          pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            children: [
              pw.Text(
                'Period Summary',
                style: pw.TextStyle(
                  fontSize: 14,
                  fontWeight: pw.FontWeight.bold,
                ),
              ),
              pw.SizedBox(height: 12),
              _buildSummaryTable(statement, currencyFormat),
              pw.SizedBox(height: 24),
            ],
          ),

          // Performance Metrics Section
          pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            children: [
              pw.Text(
                'Performance Metrics',
                style: pw.TextStyle(
                  fontSize: 14,
                  fontWeight: pw.FontWeight.bold,
                ),
              ),
              pw.SizedBox(height: 12),
              _buildPerformanceTable(statement, currencyFormat),
              pw.SizedBox(height: 24),
            ],
          ),

          // Trade List Section
          if (statement.trades.isNotEmpty)
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text(
                  'Trade Details',
                  style: pw.TextStyle(
                    fontSize: 14,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.SizedBox(height: 12),
                _buildTradeTable(statement, currencyFormat),
              ],
            ),
        ],
        footer: (context) => pw.Column(
          children: [
            pw.Divider(),
            pw.Row(
              mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
              children: [
                pw.Text(
                  'Zwesta Trading System',
                  style: const pw.TextStyle(fontSize: 8),
                ),
                pw.Text(
                  'Page ${context.pageNumber} of ${context.pagesCount}',
                  style: const pw.TextStyle(fontSize: 8),
                ),
              ],
            ),
          ],
        ),
      ),
    );

    return pdf;
  }

  static pw.Widget _buildAccountInfoTable(
    Account account,
    Statement statement,
    DateFormat dateFormat,
    NumberFormat currencyFormat,
  ) => pw.Table(
      border: pw.TableBorder.all(
        color: PdfColors.grey300,
        width: 0.5,
      ),
      columnWidths: {
        0: const pw.FlexColumnWidth(2),
        1: const pw.FlexColumnWidth(2),
        2: const pw.FlexColumnWidth(2),
        3: const pw.FlexColumnWidth(2),
      },
      children: [
        pw.TableRow(
          decoration: const pw.BoxDecoration(color: PdfColors.blue50),
          children: [
            _buildTableCell('Account Number', isBold: true),
            _buildTableCell('Currency', isBold: true),
            _buildTableCell('Status', isBold: true),
            _buildTableCell('Leverage', isBold: true),
          ],
        ),
        pw.TableRow(
          children: [
            _buildTableCell(account.accountNumber),
            _buildTableCell(account.currency),
            _buildTableCell(account.status.toUpperCase()),
            _buildTableCell(account.leverage),
          ],
        ),
      ],
    );

  static pw.Widget _buildSummaryTable(
    Statement statement,
    NumberFormat currencyFormat,
  ) => pw.Table(
      border: pw.TableBorder.all(
        color: PdfColors.grey300,
        width: 0.5,
      ),
      columnWidths: {
        0: const pw.FlexColumnWidth(2),
        1: const pw.FlexColumnWidth(2),
        2: const pw.FlexColumnWidth(2),
        3: const pw.FlexColumnWidth(2),
      },
      children: [
        pw.TableRow(
          decoration: const pw.BoxDecoration(color: PdfColors.blue50),
          children: [
            _buildTableCell('Opening Balance', isBold: true),
            _buildTableCell('Closing Balance', isBold: true),
            _buildTableCell('Total Deposits', isBold: true),
            _buildTableCell('Total Withdrawals', isBold: true),
          ],
        ),
        pw.TableRow(
          children: [
            _buildTableCell(currencyFormat.format(statement.openingBalance)),
            _buildTableCell(currencyFormat.format(statement.closingBalance)),
            _buildTableCell(currencyFormat.format(statement.totalDeposits)),
            _buildTableCell(currencyFormat.format(statement.totalWithdrawals)),
          ],
        ),
      ],
    );

  static pw.Widget _buildPerformanceTable(
    Statement statement,
    NumberFormat currencyFormat,
  ) => pw.Table(
      border: pw.TableBorder.all(
        color: PdfColors.grey300,
        width: 0.5,
      ),
      columnWidths: {
        0: const pw.FlexColumnWidth(1.5),
        1: const pw.FlexColumnWidth(1.5),
        2: const pw.FlexColumnWidth(1.5),
        3: const pw.FlexColumnWidth(1.5),
        4: const pw.FlexColumnWidth(1),
        5: const pw.FlexColumnWidth(1),
      },
      children: [
        pw.TableRow(
          decoration: const pw.BoxDecoration(color: PdfColors.blue50),
          children: [
            _buildTableCell('Total Trades', isBold: true),
            _buildTableCell('Winning', isBold: true),
            _buildTableCell('Losing', isBold: true),
            _buildTableCell('Win Rate', isBold: true),
            _buildTableCell('Largest Win', isBold: true),
            _buildTableCell('Largest Loss', isBold: true),
          ],
        ),
        pw.TableRow(
          children: [
            _buildTableCell('${statement.totalTrades}'),
            _buildTableCell('${statement.winningTrades}'),
            _buildTableCell('${statement.losingTrades}'),
            _buildTableCell('${statement.winRate.toStringAsFixed(2)}%'),
            _buildTableCell(currencyFormat.format(statement.largestWin)),
            _buildTableCell(currencyFormat.format(statement.largestLoss)),
          ],
        ),
        pw.TableRow(
          decoration: const pw.BoxDecoration(color: PdfColors.grey100),
          children: [
            _buildTableCell(''),
            _buildTableCell(''),
            _buildTableCell('Total Profit', isBold: true),
            _buildTableCell('Total Loss', isBold: true),
            _buildTableCell('Avg Win', isBold: true),
            _buildTableCell('Avg Loss', isBold: true),
          ],
        ),
        pw.TableRow(
          children: [
            _buildTableCell(''),
            _buildTableCell(''),
            _buildTableCell(currencyFormat.format(statement.totalProfit)),
            _buildTableCell(currencyFormat.format(statement.totalLoss)),
            _buildTableCell(currencyFormat.format(statement.averageWin)),
            _buildTableCell(currencyFormat.format(statement.averageLoss)),
          ],
        ),
      ],
    );

  static pw.Widget _buildTradeTable(
    Statement statement,
    NumberFormat currencyFormat,
  ) => pw.Table(
      border: pw.TableBorder.all(
        color: PdfColors.grey300,
        width: 0.5,
      ),
      columnWidths: {
        0: const pw.FlexColumnWidth(1.2),
        1: const pw.FlexColumnWidth(1),
        2: const pw.FlexColumnWidth(1),
        3: const pw.FlexColumnWidth(1.2),
        4: const pw.FlexColumnWidth(1.2),
        5: const pw.FlexColumnWidth(1.2),
        6: const pw.FlexColumnWidth(1),
      },
      children: [
        pw.TableRow(
          decoration: const pw.BoxDecoration(color: PdfColors.blue50),
          children: [
            _buildTableCell('Symbol', isBold: true),
            _buildTableCell('Type', isBold: true),
            _buildTableCell('Qty', isBold: true),
            _buildTableCell('Entry Price', isBold: true),
            _buildTableCell('Exit Price', isBold: true),
            _buildTableCell('Profit/Loss', isBold: true),
            _buildTableCell('%', isBold: true),
          ],
        ),
        ...statement.trades.map((trade) {
          final profitColor = trade.profit >= 0 ? PdfColors.green : PdfColors.red;
          return pw.TableRow(
            children: [
              _buildTableCell(trade.symbol),
              _buildTableCell(trade.type.toUpperCase()),
              _buildTableCell(trade.quantity.toStringAsFixed(0)),
              _buildTableCell(trade.entryPrice.toStringAsFixed(4)),
              _buildTableCell(trade.exitPrice.toStringAsFixed(4)),
              pw.Container(
                padding: const pw.EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                child: pw.Text(
                  currencyFormat.format(trade.profit),
                  textAlign: pw.TextAlign.right,
                  style: pw.TextStyle(
                    color: profitColor,
                    fontSize: 9,
                  ),
                ),
              ),
              _buildTableCell(
                '${trade.profitPercentage.toStringAsFixed(2)}%',
              ),
            ],
          );
        }),
      ],
    );

  static pw.Widget _buildTableCell(String text, {bool isBold = false}) => pw.Container(
      padding: const pw.EdgeInsets.symmetric(horizontal: 4, vertical: 6),
      child: pw.Text(
        text,
        textAlign: pw.TextAlign.center,
        style: pw.TextStyle(
          fontSize: 9,
          fontWeight: isBold ? pw.FontWeight.bold : pw.FontWeight.normal,
        ),
      ),
    );
}
