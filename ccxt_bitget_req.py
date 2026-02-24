    def create_order_request(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: Num = None, params={}):
        sandboxMode = self.safe_bool(self.options, 'sandboxMode', False)
        market = None
        if sandboxMode:
            sandboxSymbol = self.convert_symbol_for_sandbox(symbol)
            market = self.market(sandboxSymbol)
        else:
            market = self.market(symbol)
        marketType = None
        marginMode = None
        marketType, params = self.handle_market_type_and_params('createOrder', market, params)
        marginMode, params = self.handle_margin_mode_and_params('createOrder', params)
        request: dict = {
            'symbol': market['id'],
            'orderType': type,
        }
        isMarketOrder = type == 'market'
        triggerPrice = self.safe_value_2(params, 'stopPrice', 'triggerPrice')
        stopLossTriggerPrice = self.safe_value(params, 'stopLossPrice')
        takeProfitTriggerPrice = self.safe_value(params, 'takeProfitPrice')
        stopLoss = self.safe_value(params, 'stopLoss')
        takeProfit = self.safe_value(params, 'takeProfit')
        isTriggerOrder = triggerPrice is not None
        isStopLossTriggerOrder = stopLossTriggerPrice is not None
        isTakeProfitTriggerOrder = takeProfitTriggerPrice is not None
        isStopLoss = stopLoss is not None
        isTakeProfit = takeProfit is not None
        isStopLossOrTakeProfitTrigger = isStopLossTriggerOrder or isTakeProfitTriggerOrder
        isStopLossOrTakeProfit = isStopLoss or isTakeProfit
        trailingTriggerPrice = self.safe_string(params, 'trailingTriggerPrice', self.number_to_string(price))
        trailingPercent = self.safe_string_2(params, 'trailingPercent', 'callbackRatio')
        isTrailingPercentOrder = trailingPercent is not None
        if self.sum(isTriggerOrder, isStopLossTriggerOrder, isTakeProfitTriggerOrder, isTrailingPercentOrder) > 1:
            raise ExchangeError(self.id + ' createOrder() params can only contain one of triggerPrice, stopLossPrice, takeProfitPrice, trailingPercent')
        if type == 'limit':
            request['price'] = self.price_to_precision(symbol, price)
        triggerType = self.safe_string(params, 'triggerType', 'mark_price')
        reduceOnly = self.safe_bool(params, 'reduceOnly', False)
        clientOrderId = self.safe_string_2(params, 'clientOid', 'clientOrderId')
        exchangeSpecificTifParam = self.safe_string_2(params, 'force', 'timeInForce')
        postOnly = None
        postOnly, params = self.handle_post_only(isMarketOrder, exchangeSpecificTifParam == 'post_only', params)
        defaultTimeInForce = self.safe_string_upper(self.options, 'defaultTimeInForce')
        timeInForce = self.safe_string_upper(params, 'timeInForce', defaultTimeInForce)
        if postOnly:
            request['force'] = 'post_only'
        elif timeInForce == 'GTC':
            request['force'] = 'GTC'
        elif timeInForce == 'FOK':
            request['force'] = 'FOK'
        elif timeInForce == 'IOC':
            request['force'] = 'IOC'
        params = self.omit(params, ['stopPrice', 'triggerType', 'stopLossPrice', 'takeProfitPrice', 'stopLoss', 'takeProfit', 'postOnly', 'reduceOnly', 'clientOrderId', 'trailingPercent', 'trailingTriggerPrice'])
        if (marketType == 'swap') or (marketType == 'future'):
            request['marginCoin'] = market['settleId']
            request['size'] = self.amount_to_precision(symbol, amount)
            productType = None
            productType, params = self.handle_product_type_and_params(market, params)
            request['productType'] = productType
            if clientOrderId is not None:
                request['clientOid'] = clientOrderId
            if isTriggerOrder or isStopLossOrTakeProfitTrigger or isTrailingPercentOrder:
                request['triggerType'] = triggerType
            if isTrailingPercentOrder:
                if not isMarketOrder:
                    raise BadRequest(self.id + ' createOrder() bitget trailing orders must be market orders')
                if trailingTriggerPrice is None:
                    raise ArgumentsRequired(self.id + ' createOrder() bitget trailing orders must have a trailingTriggerPrice param')
                request['planType'] = 'track_plan'
                request['triggerPrice'] = self.price_to_precision(symbol, trailingTriggerPrice)
                request['callbackRatio'] = trailingPercent
            elif isTriggerOrder:
                request['planType'] = 'normal_plan'
                request['triggerPrice'] = self.price_to_precision(symbol, triggerPrice)
                if price is not None:
                    request['executePrice'] = self.price_to_precision(symbol, price)
                if isStopLoss:
                    slTriggerPrice = self.safe_number_2(stopLoss, 'triggerPrice', 'stopPrice')
                    request['stopLossTriggerPrice'] = self.price_to_precision(symbol, slTriggerPrice)
                    slPrice = self.safe_number(stopLoss, 'price')
                    request['stopLossExecutePrice'] = self.price_to_precision(symbol, slPrice)
                    slType = self.safe_string(stopLoss, 'type', 'mark_price')
                    request['stopLossTriggerType'] = slType
                if isTakeProfit:
                    tpTriggerPrice = self.safe_number_2(takeProfit, 'triggerPrice', 'stopPrice')
                    request['stopSurplusTriggerPrice'] = self.price_to_precision(symbol, tpTriggerPrice)
                    tpPrice = self.safe_number(takeProfit, 'price')
                    request['stopSurplusExecutePrice'] = self.price_to_precision(symbol, tpPrice)
                    tpType = self.safe_string(takeProfit, 'type', 'mark_price')
                    request['stopSurplusTriggerType'] = tpType
            elif isStopLossOrTakeProfitTrigger:
                if not isMarketOrder:
                    raise ExchangeError(self.id + ' createOrder() bitget stopLoss or takeProfit orders must be market orders')
                request['holdSide'] = 'long' if (side == 'buy') else 'short'
                if isStopLossTriggerOrder:
                    request['triggerPrice'] = self.price_to_precision(symbol, stopLossTriggerPrice)
                    request['planType'] = 'pos_loss'
                elif isTakeProfitTriggerOrder:
                    request['triggerPrice'] = self.price_to_precision(symbol, takeProfitTriggerPrice)
                    request['planType'] = 'pos_profit'
            else:
                if isStopLoss:
                    slTriggerPrice = self.safe_value_2(stopLoss, 'triggerPrice', 'stopPrice')
                    request['presetStopLossPrice'] = self.price_to_precision(symbol, slTriggerPrice)
                if isTakeProfit:
                    tpTriggerPrice = self.safe_value_2(takeProfit, 'triggerPrice', 'stopPrice')
                    request['presetStopSurplusPrice'] = self.price_to_precision(symbol, tpTriggerPrice)
            if not isStopLossOrTakeProfitTrigger:
                if marginMode is None:
                    marginMode = 'cross'
                marginModeRequest = 'crossed' if (marginMode == 'cross') else 'isolated'
                request['marginMode'] = marginModeRequest
                hedged = None
                hedged, params = self.handle_param_bool(params, 'hedged', False)
                # backward compatibility for `oneWayMode`
                oneWayMode = None
                oneWayMode, params = self.handle_param_bool(params, 'oneWayMode')
                if oneWayMode is not None:
                    hedged = not oneWayMode
                requestSide = side
                if reduceOnly:
                    if not hedged:
                        request['reduceOnly'] = 'YES'
                    else:
                        # on bitget hedge mode if the position is long the side is always buy, and if the position is short the side is always sell
                        requestSide = 'sell' if (side == 'buy') else 'buy'
                        request['tradeSide'] = 'Close'
                else:
                    if hedged:
                        request['tradeSide'] = 'Open'
                request['side'] = requestSide
        elif marketType == 'spot':
            if isStopLossOrTakeProfitTrigger or isStopLossOrTakeProfit:
                raise InvalidOrder(self.id + ' createOrder() does not support stop loss/take profit orders on spot markets, only swap markets')
            request['side'] = side
            quantity = None
            planType = None
            createMarketBuyOrderRequiresPrice = True
            createMarketBuyOrderRequiresPrice, params = self.handle_option_and_params(params, 'createOrder', 'createMarketBuyOrderRequiresPrice', True)
            if isMarketOrder and (side == 'buy'):
                planType = 'total'
                cost = self.safe_number(params, 'cost')
                params = self.omit(params, 'cost')
                if cost is not None:
                    quantity = self.cost_to_precision(symbol, cost)
                elif createMarketBuyOrderRequiresPrice:
                    if price is None:
                        raise InvalidOrder(self.id + ' createOrder() requires the price argument for market buy orders to calculate the total cost to spend(amount * price), alternatively set the createMarketBuyOrderRequiresPrice option or param to False and pass the cost to spend in the amount argument')
                    else:
                        amountString = self.number_to_string(amount)
                        priceString = self.number_to_string(price)
                        quoteAmount = Precise.string_mul(amountString, priceString)
                        quantity = self.cost_to_precision(symbol, quoteAmount)
                else:
                    quantity = self.cost_to_precision(symbol, amount)
            else:
                planType = 'amount'
                quantity = self.amount_to_precision(symbol, amount)
            if clientOrderId is not None:
                request['clientOid'] = clientOrderId
            if marginMode is not None:
                request['loanType'] = 'normal'
                if isMarketOrder and (side == 'buy'):
                    request['quoteSize'] = quantity
                else:
                    request['baseSize'] = quantity
            else:
                if quantity is not None:
                    request['size'] = quantity
                if triggerPrice is not None:
                    request['planType'] = planType
                    request['triggerType'] = triggerType
                    request['triggerPrice'] = self.price_to_precision(symbol, triggerPrice)
                    if price is not None:
                        request['executePrice'] = self.price_to_precision(symbol, price)
        else:
            raise NotSupported(self.id + ' createOrder() does not support ' + marketType + ' orders')
        return self.extend(request, params)
