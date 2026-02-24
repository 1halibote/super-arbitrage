    def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: Num = None, params={}):
        """
        create a trade order
        :see: https://www.bitget.com/api-doc/spot/trade/Place-Order
        :see: https://www.bitget.com/api-doc/spot/plan/Place-Plan-Order
        :see: https://www.bitget.com/api-doc/contract/trade/Place-Order
        :see: https://www.bitget.com/api-doc/contract/plan/Place-Tpsl-Order
        :see: https://www.bitget.com/api-doc/contract/plan/Place-Plan-Order
        :see: https://www.bitget.com/api-doc/margin/cross/trade/Cross-Place-Order
        :see: https://www.bitget.com/api-doc/margin/isolated/trade/Isolated-Place-Order
        :param str symbol: unified symbol of the market to create an order in
        :param str type: 'market' or 'limit'
        :param str side: 'buy' or 'sell'
        :param float amount: how much you want to trade in units of the base currency
        :param float [price]: the price at which the order is to be fullfilled, in units of the quote currency, ignored in market orders
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :param float [params.cost]: *spot only* how much you want to trade in units of the quote currency, for market buy orders only
        :param float [params.triggerPrice]: *swap only* The price at which a trigger order is triggered at
        :param float [params.stopLossPrice]: *swap only* The price at which a stop loss order is triggered at
        :param float [params.takeProfitPrice]: *swap only* The price at which a take profit order is triggered at
        :param dict [params.takeProfit]: *takeProfit object in params* containing the triggerPrice at which the attached take profit order will be triggered(perpetual swap markets only)
        :param float [params.takeProfit.triggerPrice]: *swap only* take profit trigger price
        :param dict [params.stopLoss]: *stopLoss object in params* containing the triggerPrice at which the attached stop loss order will be triggered(perpetual swap markets only)
        :param float [params.stopLoss.triggerPrice]: *swap only* stop loss trigger price
        :param str [params.timeInForce]: "GTC", "IOC", "FOK", or "PO"
        :param str [params.marginMode]: 'isolated' or 'cross' for spot margin trading
        :param str [params.loanType]: *spot margin only* 'normal', 'autoLoan', 'autoRepay', or 'autoLoanAndRepay' default is 'normal'
        :param str [params.holdSide]: *contract stopLossPrice, takeProfitPrice only* Two-way position: ('long' or 'short'), one-way position: ('buy' or 'sell')
        :param float [params.stopLoss.price]: *swap only* the execution price for a stop loss attached to a trigger order
        :param float [params.takeProfit.price]: *swap only* the execution price for a take profit attached to a trigger order
        :param str [params.stopLoss.type]: *swap only* the type for a stop loss attached to a trigger order, 'fill_price', 'index_price' or 'mark_price', default is 'mark_price'
        :param str [params.takeProfit.type]: *swap only* the type for a take profit attached to a trigger order, 'fill_price', 'index_price' or 'mark_price', default is 'mark_price'
        :param str [params.trailingPercent]: *swap and future only* the percent to trail away from the current market price, rate can not be greater than 10
        :param str [params.trailingTriggerPrice]: *swap and future only* the price to trigger a trailing stop order, default uses the price argument
        :param str [params.triggerType]: *swap and future only* 'fill_price', 'mark_price' or 'index_price'
        :param boolean [params.oneWayMode]: *swap and future only* required to set self to True in one_way_mode and you can leave self in hedge_mode, can adjust the mode using the setPositionMode() method
        :returns dict: an `order structure <https://docs.ccxt.com/#/?id=order-structure>`
        """
        self.load_markets()
        market = self.market(symbol)
        marginParams = self.handle_margin_mode_and_params('createOrder', params)
        marginMode = marginParams[0]
        triggerPrice = self.safe_value_2(params, 'stopPrice', 'triggerPrice')
        stopLossTriggerPrice = self.safe_value(params, 'stopLossPrice')
        takeProfitTriggerPrice = self.safe_value(params, 'takeProfitPrice')
        trailingPercent = self.safe_string_2(params, 'trailingPercent', 'callbackRatio')
        isTrailingPercentOrder = trailingPercent is not None
        isTriggerOrder = triggerPrice is not None
        isStopLossTriggerOrder = stopLossTriggerPrice is not None
        isTakeProfitTriggerOrder = takeProfitTriggerPrice is not None
        isStopLossOrTakeProfitTrigger = isStopLossTriggerOrder or isTakeProfitTriggerOrder
        request = self.create_order_request(symbol, type, side, amount, price, params)
        response = None
        if market['spot']:
            if isTriggerOrder:
                response = self.privateSpotPostV2SpotTradePlacePlanOrder(request)
            elif marginMode == 'isolated':
                response = self.privateMarginPostV2MarginIsolatedPlaceOrder(request)
            elif marginMode == 'cross':
                response = self.privateMarginPostV2MarginCrossedPlaceOrder(request)
            else:
                response = self.privateSpotPostV2SpotTradePlaceOrder(request)
        else:
            if isTriggerOrder or isTrailingPercentOrder:
                response = self.privateMixPostV2MixOrderPlacePlanOrder(request)
            elif isStopLossOrTakeProfitTrigger:
                response = self.privateMixPostV2MixOrderPlaceTpslOrder(request)
            else:
                response = self.privateMixPostV2MixOrderPlaceOrder(request)
        #
        #     {
        #         "code": "00000",
        #         "msg": "success",
        #         "requestTime": 1645932209602,
        #         "data": {
        #             "orderId": "881669078313766912",
        #             "clientOid": "iauIBf#a45b595f96474d888d0ada"
        #         }
        #     }
        #
        data = self.safe_dict(response, 'data', {})
        return self.parse_order(data, market)
