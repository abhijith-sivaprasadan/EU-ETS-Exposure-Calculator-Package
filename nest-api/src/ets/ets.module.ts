import { Module } from '@nestjs/common';
import { EtsController } from './ets.controller';
import { EtsService } from './ets.service';

@Module({
  controllers: [EtsController],
  providers: [EtsService],
})
export class EtsModule {}
