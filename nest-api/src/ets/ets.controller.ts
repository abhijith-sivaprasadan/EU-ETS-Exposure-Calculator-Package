import {
  BadRequestException,
  Body,
  Controller,
  Header,
  HttpCode,
  Post,
  StreamableFile,
  UploadedFile,
  UploadedFiles,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor, FilesInterceptor } from '@nestjs/platform-express';
import { memoryStorage } from 'multer';
import { EtsService } from './ets.service';

@Controller('ets')
export class EtsController {
  constructor(private readonly etsService: EtsService) {}

  @Post('analyze')
  @HttpCode(200)
  @UseInterceptors(
    FileInterceptor('workbook', {
      storage: memoryStorage(),
      limits: { fileSize: 15 * 1024 * 1024 },
    }),
  )
  analyzeSingle(@UploadedFile() workbook: Express.Multer.File, @Body() body: Record<string, string>) {
    if (!workbook) {
      throw new BadRequestException('Missing workbook upload (field name: workbook).');
    }
    return this.etsService.analyzeWorkbook(workbook.originalname, workbook.buffer, {
      selectedScenario: body.selectedScenario,
      customEuaPrice: body.customEuaPrice ? Number(body.customEuaPrice) : undefined,
      basePrice: body.basePrice ? Number(body.basePrice) : undefined,
      stressPrice: body.stressPrice ? Number(body.stressPrice) : undefined,
      highPrice: body.highPrice ? Number(body.highPrice) : undefined,
      scope3FactorTco2PerT: body.scope3FactorTco2PerT
        ? Number(body.scope3FactorTco2PerT)
        : undefined,
      freeAllocationTco2: body.freeAllocationTco2 ? Number(body.freeAllocationTco2) : undefined,
      measureReductionPct: body.measureReductionPct ? Number(body.measureReductionPct) : undefined,
      measureAnnualizedCostEur: body.measureAnnualizedCostEur
        ? Number(body.measureAnnualizedCostEur)
        : undefined,
    });
  }

  @Post('report')
  @HttpCode(200)
  @Header('Content-Type', 'application/pdf')
  @UseInterceptors(
    FileInterceptor('workbook', {
      storage: memoryStorage(),
      limits: { fileSize: 15 * 1024 * 1024 },
    }),
  )
  buildSingleReport(
    @UploadedFile() workbook: Express.Multer.File,
    @Body() body: Record<string, string>,
  ) {
    if (!workbook) {
      throw new BadRequestException('Missing workbook upload (field name: workbook).');
    }
    const pdf = this.etsService.buildPdfReportFromWorkbook(
      workbook.originalname,
      workbook.buffer,
      {
        selectedScenario: body.selectedScenario,
        customEuaPrice: body.customEuaPrice ? Number(body.customEuaPrice) : undefined,
        basePrice: body.basePrice ? Number(body.basePrice) : undefined,
        stressPrice: body.stressPrice ? Number(body.stressPrice) : undefined,
        highPrice: body.highPrice ? Number(body.highPrice) : undefined,
        scope3FactorTco2PerT: body.scope3FactorTco2PerT
          ? Number(body.scope3FactorTco2PerT)
          : undefined,
        freeAllocationTco2: body.freeAllocationTco2 ? Number(body.freeAllocationTco2) : undefined,
        measureReductionPct: body.measureReductionPct ? Number(body.measureReductionPct) : undefined,
        measureAnnualizedCostEur: body.measureAnnualizedCostEur
          ? Number(body.measureAnnualizedCostEur)
          : undefined,
      },
      body.reportOwner,
    );
    return new StreamableFile(pdf, {
      disposition: 'attachment; filename="ets_management_report.pdf"',
    });
  }

  @Post('portfolio')
  @HttpCode(200)
  @UseInterceptors(
    FilesInterceptor('workbooks', 30, {
      storage: memoryStorage(),
      limits: { fileSize: 15 * 1024 * 1024 },
    }),
  )
  analyzePortfolio(@UploadedFiles() workbooks: Express.Multer.File[], @Body() body: Record<string, string>) {
    if (!workbooks || workbooks.length === 0) {
      throw new BadRequestException('Missing workbook uploads (field name: workbooks).');
    }

    return this.etsService.analyzePortfolio(
      workbooks.map((f) => ({ name: f.originalname, buffer: f.buffer })),
      {
        selectedScenario: body.selectedScenario,
        customEuaPrice: body.customEuaPrice ? Number(body.customEuaPrice) : undefined,
        basePrice: body.basePrice ? Number(body.basePrice) : undefined,
        stressPrice: body.stressPrice ? Number(body.stressPrice) : undefined,
        highPrice: body.highPrice ? Number(body.highPrice) : undefined,
        scope3FactorTco2PerT: body.scope3FactorTco2PerT
          ? Number(body.scope3FactorTco2PerT)
          : undefined,
        freeAllocationTco2: body.freeAllocationTco2 ? Number(body.freeAllocationTco2) : undefined,
        measureReductionPct: body.measureReductionPct ? Number(body.measureReductionPct) : undefined,
        measureAnnualizedCostEur: body.measureAnnualizedCostEur
          ? Number(body.measureAnnualizedCostEur)
          : undefined,
      },
      {
        amberThresholdEur: body.amberThresholdEur ? Number(body.amberThresholdEur) : 4_000_000,
        redThresholdEur: body.redThresholdEur ? Number(body.redThresholdEur) : 6_000_000,
      },
    );
  }
}
